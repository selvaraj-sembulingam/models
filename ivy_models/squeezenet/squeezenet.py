from ivy_models.helpers import load_torch_weights
import ivy


class SqueezeNetFire(ivy.Module):
    def __init__(
        self,
        inplanes: int,
        squeeze_planes: int,
        expand1x1_planes: int,
        expand3x3_planes: int,
    ) -> None:
        self.inplanes = inplanes
        self.squeeze_planes = squeeze_planes
        self.expand1x1_planes = expand1x1_planes
        self.expand3x3_planes = expand3x3_planes
        super().__init__()

    def _build(self, *args, **kwargs):
        self.squeeze = ivy.Conv2D(
            self.inplanes, self.squeeze_planes, [1, 1], 1, 0, data_format="NCHW"
        )
        self.squeeze_activation = ivy.ReLU()
        self.expand1x1 = ivy.Conv2D(
            self.squeeze_planes, self.expand1x1_planes, [1, 1], 1, 0, data_format="NCHW"
        )
        self.expand1x1_activation = ivy.ReLU()
        self.expand3x3 = ivy.Conv2D(
            self.squeeze_planes, self.expand3x3_planes, [3, 3], 1, 1, data_format="NCHW"
        )
        self.expand3x3_activation = ivy.ReLU()

    def _forward(self, x):
        x = self.squeeze_activation(self.squeeze(x))
        return ivy.concat(
            [
                self.expand1x1_activation(self.expand1x1(x)),
                self.expand3x3_activation(self.expand3x3(x)),
            ],
            axis=1,
        )


class SqueezeNet(ivy.Module):
    def __init__(
        self,
        version: str = "1_0",
        num_classes: int = 1000,
        dropout: float = 0.5,
        v=None,
    ) -> None:
        self.version = version
        self.num_classes = num_classes
        self.dropout = dropout
        super().__init__(v=v)

    def _build(self, *args, **kwargs):
        if self.version == "1_0":
            self.features = ivy.Sequential(
                ivy.Conv2D(3, 96, [7, 7], 2, 0, data_format="NCHW"),
                ivy.ReLU(),
                ivy.MaxPool2D(3, 2, 0, data_format="NCHW"),
                SqueezeNetFire(96, 16, 64, 64),
                SqueezeNetFire(128, 16, 64, 64),
                SqueezeNetFire(128, 32, 128, 128),
                ivy.MaxPool2D(3, 2, 0, data_format="NCHW"),
                SqueezeNetFire(256, 32, 128, 128),
                SqueezeNetFire(256, 48, 192, 192),
                SqueezeNetFire(384, 48, 192, 192),
                SqueezeNetFire(384, 64, 256, 256),
                ivy.MaxPool2D(3, 2, 0, data_format="NCHW"),
                SqueezeNetFire(512, 64, 256, 256),
            )
        elif self.version == "1_1":
            self.features = ivy.Sequential(
                ivy.Conv2D(3, 64, [3, 3], 2, 0, data_format="NCHW"),
                ivy.ReLU(),
                ivy.MaxPool2D(3, 2, 0, data_format="NCHW"),
                SqueezeNetFire(64, 16, 64, 64),
                SqueezeNetFire(128, 16, 64, 64),
                ivy.MaxPool2D(3, 2, 0, data_format="NCHW"),
                SqueezeNetFire(128, 32, 128, 128),
                SqueezeNetFire(256, 32, 128, 128),
                ivy.MaxPool2D(3, 2, 0, data_format="NCHW"),
                SqueezeNetFire(256, 48, 192, 192),
                SqueezeNetFire(384, 48, 192, 192),
                SqueezeNetFire(384, 64, 256, 256),
                SqueezeNetFire(512, 64, 256, 256),
            )
        else:
            raise ValueError(
                f"Unsupported SqueezeNet version {self.version}: 1_0 or 1_1 expected"
            )

        # Final convolution is initialized differently from the rest
        final_conv = ivy.Conv2D(512, self.num_classes, [1, 1], 1, 0, data_format="NCHW")
        self.classifier = ivy.Sequential(
            ivy.Dropout(prob=self.dropout),
            final_conv,
            ivy.ReLU(),
            ivy.AdaptiveAvgPool2d((1, 1)),
        )

    def _forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return ivy.flatten(x, start_dim=1)


def _squeezenet_torch_weights_mapping(old_key, new_key):
    new_mapping = new_key
    if "weight" in old_key:
        new_mapping = {"key_chain": new_key, "pattern": "b c h w -> h w c b"}
    elif "bias" in old_key:
        new_mapping = {"key_chain": new_key, "pattern": "h -> 1 h 1 1"}

    return new_mapping


def squeezenet(
    version: str = "1_0",
    num_classes: int = 1000,
    dropout: float = 0.5,
    v=None,
    pretrained=True,
):
    if not pretrained:
        return SqueezeNet(version, num_classes, dropout, v=v)

    reference_model = SqueezeNet(version, num_classes, dropout, v=v)
    if version == "1_0":
        url = "https://download.pytorch.org/models/squeezenet1_0-b66bff10.pth"
    elif version == "1_1":
        url = "https://download.pytorch.org/models/squeezenet1_1-b8a52dc0.pth"
    else:
        raise ValueError(
            f"Unsupported SqueezeNet version {version}: 1_0 or 1_1 expected"
        )
    w_clean = load_torch_weights(
        url,
        reference_model,
        raw_keys_to_prune=["num_batches_tracked"],
        custom_mapping=_squeezenet_torch_weights_mapping,
    )
    return SqueezeNet(version, num_classes, dropout, v=w_clean)
