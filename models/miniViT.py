import torch
import torch.nn as nn

from .ffc import FFC
from .layers import PatchTransformerEncoder, PixelWiseDotProduct


class mViT(nn.Module):
    def __init__(self, in_channels, n_query_channels=128, patch_size=16, dim_out=256,
                 embedding_dim=128, num_heads=4, norm='linear'):
        super(mViT, self).__init__()
        self.norm = norm
        self.n_query_channels = n_query_channels
        self.patch_transformer = PatchTransformerEncoder(in_channels, patch_size, embedding_dim, num_heads)
        self.dot_product_layer = PixelWiseDotProduct()

        self.conv3x3 = nn.Conv2d(in_channels, embedding_dim, kernel_size=3, stride=1, padding=1)
        self.regressor = nn.Sequential(nn.Linear(embedding_dim, 256),
                                       nn.LeakyReLU(),
                                       nn.Linear(256, 256),
                                       nn.LeakyReLU(),
                                       nn.Linear(256, dim_out))
        
        self.FFC1 = FFC(in_channels=128, out_channels=128, kernel_size=3, padding=1, ratio_gin=0.5, ratio_gout=0.5)
        self.FFC2 = FFC(in_channels=128, out_channels=128, kernel_size=3, padding=1, ratio_gin=0.5, ratio_gout=0.5)

        self.FFC3 = FFC(in_channels=128, out_channels=128, kernel_size=3, padding=1, ratio_gin=0.5, ratio_gout=0.5)
        self.FFC4 = FFC(in_channels=128, out_channels=128, kernel_size=3, padding=1, ratio_gin=0.5, ratio_gout=0.5)

        self.FFC5 = FFC(in_channels=128, out_channels=128, kernel_size=3, padding=1, ratio_gin=0.5, ratio_gout=0.5)
        self.FFC6 = FFC(in_channels=128, out_channels=128, kernel_size=3, padding=1, ratio_gin=0.5, ratio_gout=0.5)

        self.FFC7 = FFC(in_channels=128, out_channels=128, kernel_size=3, padding=1, ratio_gin=0.5, ratio_gout=0.5)
        self.FFC8 = FFC(in_channels=128, out_channels=128, kernel_size=3, padding=1, ratio_gin=0.5, ratio_gout=0.5)

    def forward(self, x):
        # n, c, h, w = x.size()
        tgt = self.patch_transformer(x.clone())  # .shape = S, N, E
        
        x_residual = x
        # 2, 128, 176, 352
        # add fourier layer
        x_l, x_g = self.FFC1((x[:, :64, :, :], x[:, 64:, :, :]))
        x_l, x_g = self.FFC2((x_l, x_g))
        x_l, x_g = self.FFC3((x_l, x_g))
        x_l, x_g = self.FFC4((x_l, x_g))

        x_l, x_g = self.FFC5((x_l, x_g))
        x_l, x_g = self.FFC6((x_l, x_g))
        x_l, x_g = self.FFC7((x_l, x_g))
        x_l, x_g = self.FFC8((x_l, x_g))

        x = torch.cat((x_l, x_g), dim=1)

        x = x + x_residual
        x = self.conv3x3(x)


        regression_head, queries = tgt[0, ...], tgt[1:self.n_query_channels + 1, ...]

        # Change from S, N, E to N, S, E
        queries = queries.permute(1, 0, 2)
        range_attention_maps = self.dot_product_layer(x, queries)  # .shape = n, n_query_channels, h, w

        y = self.regressor(regression_head)  # .shape = N, dim_out
        if self.norm == 'linear':
            y = torch.relu(y)
            eps = 0.1
            y = y + eps
        elif self.norm == 'softmax':
            return torch.softmax(y, dim=1), range_attention_maps
        else:
            y = torch.sigmoid(y)
        y = y / y.sum(dim=1, keepdim=True)
        return y, range_attention_maps
