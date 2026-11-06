"""Map of wind turbines and the ECMWF IFS HRES 9 km grid (O1280) around them.

Grid points
-----------
The O1280 octahedral reduced Gaussian grid is computed exactly, so nothing has to be downloaded:
  * 2 x 1280 latitude rows at the Gaussian latitudes (roots of the Legendre polynomial P_2560),
  * row i, counted from the nearest pole, has 4*i + 16 equally spaced points starting at 0° E.
The values match ECMWF's O1280 table (e.g. row 462: 57.539541° N, 1864 points).

Grid cells
----------
The IFS stores values at grid points; it has no official cell polygons. The cells drawn here are
the areas in which each grid point is the nearest one (spherical Voronoi polygons, great-circle
distance). They show exactly which grid point a "nearest grid point" selection takes for any
location on the map.

Usage
-----
    python ifs_grid_map.py --turbines Hill_of_Towie_turbine_metadata.csv
    python ifs_grid_map.py --turbines meta.csv --lat 57.49891107 --lon = -3.07812382	 --out-dir ../figures
    python ifs_grid_map.py --turbines meta.csv --no-tiles     # without the OpenStreetMap background

The turbine file must have the columns Latitude and Longitude (other names: --lat-col / --lon-col).
Outputs (in --out-dir, created if missing):
    ifs_grid_map_<lat>N_<lon>W.png        the map
    ifs_grid_nearest_<lat>N_<lon>W.csv    nearest grid point of every turbine

Requires: numpy, pandas, scipy, matplotlib, cartopy (pip install cartopy).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import SphericalVoronoi
from scipy.special import roots_legendre

N_GAUSS = 1280                       # O1280: 1280 latitude rows per hemisphere (IFS HRES, ~9 km)
ID_CANDIDATES = ["Turbine", "Turbine Name", "StationId", "Station", "Name", "ID"]

# chart colours
BLUE, ORANGE, INK, INK2, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#898781"


# --------------------------------------------------------------------------- grid
def gaussian_latitudes(n: int = N_GAUSS) -> np.ndarray:
    """Gaussian latitudes in degrees, from north to south (2n values)."""
    x, _ = roots_legendre(2 * n)
    return np.degrees(np.arcsin(x))[::-1]


def octahedral_grid(lat_min, lat_max, lon_min, lon_max, n: int = N_GAUSS) -> pd.DataFrame:
    """All O-grid points inside a box. Longitudes are returned in -180..180."""
    rows = []
    for k, lat in enumerate(gaussian_latitudes(n), start=1):     # k = 1 next to the north pole
        if not lat_min <= lat <= lat_max:
            continue
        i = k if k <= n else 2 * n + 1 - k                         # row number from the nearest pole
        nlon = 4 * i + 16
        lon = (np.arange(nlon) * 360.0 / nlon + 180) % 360 - 180
        lon = lon[(lon >= lon_min) & (lon <= lon_max)]
        rows.append(pd.DataFrame({"lat": lat, "lon": lon, "row": k, "points_in_row": nlon}))
    return pd.concat(rows, ignore_index=True)


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lon2) - lon1) / 2) ** 2)
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def nearest_points(grid: pd.DataFrame, lat: float, lon: float, k: int = 1) -> pd.DataFrame:
    """The k grid points nearest to (lat, lon), with their distance in km."""
    d = haversine_km(lat, lon, grid["lat"].to_numpy(), grid["lon"].to_numpy())
    idx = np.argsort(d)[:k]
    return grid.iloc[idx].assign(dist_km=d[idx])


def grid_cells(grid: pd.DataFrame, keep) -> dict:
    """Nearest-point cells (spherical Voronoi) as {grid index: (lons, lats)} for the points in `keep`."""
    lat, lon = np.radians(grid["lat"].to_numpy()), np.radians(grid["lon"].to_numpy())
    xyz = np.c_[np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
    sv = SphericalVoronoi(xyz, radius=1.0)
    sv.sort_vertices_of_regions()
    cells = {}
    for i in keep:
        v = sv.vertices[sv.regions[i]]
        cells[i] = (np.degrees(np.arctan2(v[:, 1], v[:, 0])), np.degrees(np.arcsin(v[:, 2])))
    return cells


# --------------------------------------------------------------------------- turbines
def load_turbines(path, lat_col="Latitude", lon_col="Longitude", id_col=None) -> pd.DataFrame:
    """Read turbine positions from a CSV with latitude and longitude columns."""
    t = pd.read_csv(path)
    missing = [c for c in (lat_col, lon_col) if c not in t.columns]
    if missing:
        raise ValueError(f"Columns {missing} not found in {path}. Available: {list(t.columns)}")
    id_col = id_col or next((c for c in ID_CANDIDATES if c in t.columns), None)
    ids = t[id_col].astype(str) if id_col else pd.Series([f"T{i + 1:02d}" for i in range(len(t))])
    return pd.DataFrame({"id": ids.to_numpy(), "lat": t[lat_col].astype(float).to_numpy(),
                         "lon": t[lon_col].astype(float).to_numpy()})


# --------------------------------------------------------------------------- map
def draw_map(grid, cells, turbines, study, near, extent, tiles: bool, zoom: int):
    import cartopy.crs as ccrs
    import cartopy.io.img_tiles as cimgt

    pc = ccrs.PlateCarree()
    tiler = cimgt.OSM() if tiles else None
    fig = plt.figure(figsize=(9, 9))
    ax = fig.add_subplot(1, 1, 1, projection=tiler.crs if tiles else ccrs.Mercator.GOOGLE)
    ax.set_extent(extent, crs=pc)
    if tiles:
        ax.add_image(tiler, zoom, alpha=0.55)
        ax.text(0.99, 0.005, "© OpenStreetMap contributors", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=7, color=INK2)

    # cells: outline of every visible cell, the chosen cell filled
    n0 = near.iloc[0]
    for i, (x, y) in cells.items():
        ax.fill(x, y, facecolor="none", edgecolor=MUTED, lw=0.6, transform=pc, zorder=2)
    x, y = cells[near.index[0]]
    ax.fill(x, y, color=ORANGE, alpha=0.15, lw=0, transform=pc, zorder=2,
            label="grid cell used for the study")

    ax.scatter(grid["lon"], grid["lat"], s=14, color=INK2, transform=pc, zorder=3,
               label="IFS HRES grid points (O1280, ~9 km)")
    if turbines is not None and len(turbines):
        used = turbines.drop_duplicates(["grid_lat", "grid_lon"])
        ax.scatter(used["grid_lon"], used["grid_lat"], s=110, facecolor="none", edgecolor=BLUE, lw=1.4,
                   transform=pc, zorder=4, label="grid points nearest to a turbine")
        ax.scatter(turbines["lon"], turbines["lat"], marker="^", s=45, color=BLUE, edgecolor="white",
                   lw=0.6, transform=pc, zorder=5, label="wind turbines")

    ax.plot([study["lon"], n0["lon"]], [study["lat"], n0["lat"]], color=ORANGE, lw=1.2, ls="--",
            transform=pc, zorder=5)
    ax.scatter(n0["lon"], n0["lat"], s=190, facecolor="none", edgecolor=ORANGE, lw=2.2, transform=pc,
               zorder=6, label="nearest grid point to the study location")
    ax.scatter(study["lon"], study["lat"], marker="*", s=260, color=ORANGE, edgecolor="white", lw=0.8,
               transform=pc, zorder=7, label="study location")
    ax.annotate(f"{n0['lat']:.4f}° N, {abs(n0['lon']):.4f}° {'W' if n0['lon'] < 0 else 'E'}\n"
                f"{n0['dist_km']:.2f} km from study location",
                xy=(n0["lon"], n0["lat"]), xycoords=pc._as_mpl_transform(ax),
                xytext=(12, -28), textcoords="offset points", fontsize=8.5, color=INK,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.85), zorder=8)

    # scale bar (5 km) in the lower left corner
    lon0 = extent[0] + 0.06 * (extent[1] - extent[0])
    lat0 = extent[2] + 0.05 * (extent[3] - extent[2])
    dlon = 5 / (111.32 * np.cos(np.radians(lat0)))
    ax.plot([lon0, lon0 + dlon], [lat0, lat0], color=INK, lw=3, transform=pc, zorder=8,
            solid_capstyle="butt")
    ax.text(lon0 + dlon / 2, lat0 + 0.012 * (extent[3] - extent[2]), "5 km", ha="center",
            va="bottom", fontsize=8, color=INK, transform=pc, zorder=8)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color=MUTED, alpha=0.5, linestyle=":")
    gl.top_labels = gl.right_labels = False
    ax.set_title("Wind turbines and the ECMWF IFS HRES 9 km grid", fontsize=12, fontweight="bold", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2, frameon=False, fontsize=8.5)
    fig.tight_layout()
    return fig


def save_map(out, tiles, **kw):
    """Draw with the OpenStreetMap background if it can be reached, otherwise without it."""
    if tiles:
        import cartopy.io.img_tiles as cimgt
        from urllib.request import Request, urlopen
        osm = cimgt.OSM()
        try:                                       # one test tile: is the tile server reachable?
            urlopen(Request(osm._image_url((0, 0, 0)), headers={"User-Agent": osm.user_agent}),
                    timeout=10).close()
        except Exception as e:
            print(f"Map background not reachable ({type(e).__name__}); drawing without it.")
            tiles = False
    fig = draw_map(tiles=tiles, **kw)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return tiles

		
# --------------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--turbines", help="CSV with Latitude and Longitude columns")
    p.add_argument("--lat", type=float, default=57.49891107, help="study location latitude")
    p.add_argument("--lon", type=float, default=-3.07812382, help="study location longitude")
    p.add_argument("--out-dir", default="figures", help="output folder (created if missing)")
    p.add_argument("--pad", type=float, default=0.15, help="map margin around the points, degrees latitude")
    p.add_argument("--zoom", type=int, default=11, help="zoom level of the map background")
    p.add_argument("--no-tiles", action="store_true", help="do not load the OpenStreetMap background")
    p.add_argument("--lat-col", default="Latitude")
    p.add_argument("--lon-col", default="Longitude")
    p.add_argument("--id-col", default=None, help="turbine name column (optional)")
    a = p.parse_args()

    out_dir = Path("../data/")
    tag = f"{abs(a.lat):.3f}{'N' if a.lat >= 0 else 'S'}_{abs(a.lon):.3f}{'E' if a.lon >= 0 else 'W'}"
    png_path = out_dir / f"ifs_grid_map_{tag}.png"
    #csv_path = out_dir / f"ifs_grid_nearest_{tag}.csv"

    turbines = load_turbines(a.turbines, a.lat_col, a.lon_col, a.id_col) if a.turbines else None
    lats = [a.lat] + ([] if turbines is None else turbines["lat"].tolist())
    lons = [a.lon] + ([] if turbines is None else turbines["lon"].tolist())

    # map extent (square on the ground); the grid covers a wider box so that all visible cells are complete
    pad_lon = a.pad / np.cos(np.radians(np.mean(lats)))
    extent = [min(lons) - pad_lon, max(lons) + pad_lon, min(lats) - a.pad, max(lats) + a.pad]
    grid = octahedral_grid(extent[2] - 0.3, extent[3] + 0.3, extent[0] - 0.6, extent[1] + 0.6)
    visible = grid.index[grid["lat"].between(extent[2] - 0.1, extent[3] + 0.1)
                         & grid["lon"].between(extent[0] - 0.2, extent[1] + 0.2)]
    cells = grid_cells(grid, visible)

    study = {"lat": a.lat, "lon": a.lon}
    near = nearest_points(grid, a.lat, a.lon, k=4)
    print(f"\nStudy location {a.lat:.4f}, {a.lon:.4f}: the 4 nearest O1280 grid points")
    print(near[["lat", "lon", "row", "points_in_row", "dist_km"]].round(6).to_string(index=False))

    if turbines is not None:
        nn = pd.DataFrame([nearest_points(grid, r.lat, r.lon).iloc[0] for r in turbines.itertuples()])
        turbines["grid_lat"] = nn["lat"].to_numpy()
        turbines["grid_lon"] = nn["lon"].to_numpy()
        turbines["dist_km"] = nn["dist_km"].to_numpy()
        #turbines.to_csv(csv_path, index=False)
        print(f"\n{len(turbines)} turbines -> nearest grid point")
        print(turbines.round(6).to_string(index=False))
        counts = turbines.groupby(["grid_lat", "grid_lon"]).size().rename("turbines").reset_index()
        print(f"\nThe turbines fall into {len(counts)} grid cell(s):")
        print(counts.round(6).to_string(index=False))
        c_lat, c_lon = turbines["lat"].mean(), turbines["lon"].mean()
        print(f"\nFarm centre {c_lat:.4f}, {c_lon:.4f}; distance to study location "
              f"{haversine_km(a.lat, a.lon, c_lat, c_lon):.2f} km")

    used_tiles = save_map(png_path, tiles=not a.no_tiles, grid=grid, cells=cells, turbines=turbines,
                          study=study, near=near, extent=extent, zoom=a.zoom)
    print(f"\nMap saved to {png_path.resolve()} ({'with' if used_tiles else 'without'} map background)")
#    if turbines is not None:
#        print(f"Turbine table saved to {csv_path.resolve()}")


if __name__ == "__main__":
    main()
