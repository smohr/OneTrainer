import lpips
import torch

class LpipsModelLoader:
    def __init__(self, device, net: str = "vgg"):
        self.device = device
        self.net = net

    def load(self):
        model = lpips.LPIPS(net=self.net).eval().to(self.device)
        model.requires_grad_(False)
        return model