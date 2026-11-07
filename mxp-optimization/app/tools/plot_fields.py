"""Module with implementation of field plots for the Deforming Bubble app.

    python3 tools/plot_fields.py [outdir] [--stride N] [--no-gif]      # default: out

Reads the dfun_<step>.pvti frames in <outdir> (written by src/io.cpp),
reassembles each from its per-rank .vti pieces, and draws the phi = 0 contour
over the velocity field. Writes fields_<step>.png per frame and fields.gif.
"""

import argparse
import os
import re
import xml.etree.ElementTree as ET

import numpy
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # pylint: disable=wrong-import-position


def read_frame(filename):  # pylint: disable=too-many-locals
    """
    Reassemble one .pvti frame from its .vti pieces

    Returns
    -------
    (origin, spacing, time, {name : 2D array shaped (ny, nx)})
    """
    image = ET.parse(filename).getroot().find("PImageData")
    whole = [int(value) for value in image.get("WholeExtent").split()]
    origin = [float(value) for value in image.get("Origin").split()]
    spacing = [float(value) for value in image.get("Spacing").split()]
    time = float(image.find("FieldData/DataArray[@Name='TIME']").text)

    names = [array.get("Name") for array in image.findall("PCellData/PDataArray")]
    fields = {name: numpy.full((whole[3], whole[1]), numpy.nan) for name in names}

    for piece in image.findall("Piece"):
        source = os.path.join(os.path.dirname(filename), piece.get("Source"))
        ilo, ihi, jlo, jhi = [int(value) for value in piece.get("Extent").split()[:4]]
        for array in ET.parse(source).getroot().findall(".//CellData/DataArray"):
            values = numpy.array(array.text.split(), dtype=float)
            fields[array.get("Name")][jlo:jhi, ilo:ihi] = values.reshape(
                jhi - jlo, ihi - ilo
            )

    for name, field in fields.items():
        if numpy.isnan(field).any():
            raise ValueError(f"[plot_fields] {filename}: '{name}' not fully covered")

    return origin, spacing, time, fields


def plot_frame(filename, outdir, step):  # pylint: disable=too-many-locals
    """
    phi = 0 contour over |u| and velocity arrows for one frame

    Returns
    -------
    path to the png
    """
    origin, spacing, time, fields = read_frame(filename)
    nrows, ncols = fields["dfun"].shape
    xcoord = origin[0] + (numpy.arange(ncols) + 0.5) * spacing[0]
    ycoord = origin[1] + (numpy.arange(nrows) + 0.5) * spacing[1]
    xgrid, ygrid = numpy.meshgrid(xcoord, ycoord)

    fig, axis = plt.subplots(figsize=(6, 5.4))

    speed = numpy.hypot(fields["u"], fields["v"])
    fig.colorbar(axis.pcolormesh(xgrid, ygrid, speed, cmap="Blues"), label="|u|")

    skip = slice(None, None, max(1, ncols // 24))
    axis.quiver(
        xgrid[skip, skip],
        ygrid[skip, skip],
        fields["u"][skip, skip],
        fields["v"][skip, skip],
        color="0.35",
    )
    axis.contour(xgrid, ygrid, fields["dfun"], levels=[0.0], colors="crimson")

    axis.set_aspect("equal")
    axis.set_title(f"step {step}   t = {time:.4f}   phi = 0")

    png = os.path.join(outdir, f"fields_{step:06d}.png")
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    plt.close(fig)
    return png


def write_gif(pngs, outdir):
    """
    Animated gif of the frames, written to <outdir>/fields.gif
    """
    from PIL import Image  # pylint: disable=import-outside-toplevel

    images = [
        Image.open(png).convert("P", palette=Image.Palette.ADAPTIVE) for png in pngs
    ]
    gif = os.path.join(outdir, "fields.gif")
    images[0].save(gif, save_all=True, append_images=images[1:], duration=120, loop=0)
    return gif


def main():
    """
    Plot every (stride-th) frame of one output directory
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("outdir", nargs="?", default="out")
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--no-gif", action="store_true")
    args = parser.parse_args()

    frames = []
    for name in sorted(os.listdir(args.outdir)):
        match = re.fullmatch(r"dfun_(\d+)\.pvti", name)
        if match:
            frames.append((int(match.group(1)), os.path.join(args.outdir, name)))

    if not frames:
        raise SystemExit(f"[plot_fields] no dfun_*.pvti in {args.outdir}")

    pngs = [
        plot_frame(filename, args.outdir, step)
        for step, filename in sorted(frames)[:: args.stride]
    ]
    print(f"[plot_fields] wrote {len(pngs)} frame(s) into {args.outdir}")

    if not args.no_gif:
        print(f"[plot_fields] wrote {write_gif(pngs, args.outdir)}")


if __name__ == "__main__":
    main()
