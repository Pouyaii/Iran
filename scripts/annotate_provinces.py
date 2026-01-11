import json
import math
import re
from pathlib import Path

INDEX_PATH = Path("index.html")
PROVINCES_PATH = Path("data/iran-provinces.geojson")

VERIFIED_PATTERN = re.compile(
    r"const verifiedIncidents = useMemo\(\(\) => \[(.*?)\n\s*\], \[\]\);",
    re.DOTALL,
)
UNVERIFIED_PATTERN = re.compile(
    r"const unverifiedIncidents = useMemo\(\(\) => \[(.*?)\n\s*\], \[\]\);",
    re.DOTALL,
)

PROVINCE_CENTERS = {
    "Tehran": (35.6892, 51.3890),
    "Qom": (34.6416, 50.8746),
    "Alborz": (35.8400, 50.9391),
    "Isfahan": (32.6546, 51.6680),
    "Fars": (29.5918, 52.5836),
    "Khorasan Razavi": (36.2605, 59.6168),
    "East Azerbaijan": (38.0800, 46.2919),
    "West Azerbaijan": (37.5527, 45.0760),
    "Ardabil": (38.2498, 48.2933),
    "Gilan": (37.2808, 49.5832),
    "Mazandaran": (36.5651, 53.0586),
    "Golestan": (36.8456, 54.4398),
    "Zanjan": (36.6769, 48.4963),
    "Qazvin": (36.2688, 50.0041),
    "Markazi": (34.0917, 49.6892),
    "Hamedan": (34.7981, 48.5146),
    "Kermanshah": (34.3142, 47.0650),
    "Kurdistan": (35.3219, 46.9862),
    "Ilam": (33.6374, 46.4227),
    "Lorestan": (33.4878, 48.3558),
    "Khuzestan": (31.3183, 48.6706),
    "Chaharmahal and Bakhtiari": (32.3256, 50.8644),
    "Kohgiluyeh and Boyer-Ahmad": (30.6682, 51.5873),
    "Bushehr": (28.9234, 50.8203),
    "Hormozgan": (27.1832, 56.2666),
    "Sistan and Baluchestan": (29.4963, 60.8629),
    "Kerman": (30.2839, 57.0834),
    "Yazd": (31.8974, 54.3569),
    "Semnan": (35.5770, 53.3886),
    "North Khorasan": (37.4692, 57.3333),
    "South Khorasan": (32.8650, 59.2211),
}


def point_in_ring(point, ring):
    x, y = point
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def point_in_polygon(point, polygon):
    if not point_in_ring(point, polygon[0]):
        return False
    for hole in polygon[1:]:
        if point_in_ring(point, hole):
            return False
    return True


def point_in_geometry(point, geometry):
    if geometry["type"] == "Polygon":
        return point_in_polygon(point, geometry["coordinates"])
    if geometry["type"] == "MultiPolygon":
        return any(point_in_polygon(point, poly) for poly in geometry["coordinates"])
    return False


def load_provinces():
    data = json.loads(PROVINCES_PATH.read_text())
    return [
        {
            "name": feature["properties"].get("name", "Unknown"),
            "geometry": feature["geometry"],
        }
        for feature in data["features"]
    ]


def distance(point_a, point_b):
    return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])


def annotate_incidents(incidents, provinces):
    unknown = []
    updated = []
    for incident in incidents:
        lat, lon = incident["coords"]
        point = (lon, lat)
        matches = [
            province for province in provinces if point_in_geometry(point, province["geometry"])
        ]
        if matches:
            province_name = min(
                matches,
                key=lambda province: distance((lat, lon), PROVINCE_CENTERS.get(province["name"], (lat, lon))),
            )["name"]
        else:
            province_name = "Unknown"
        if province_name == "Unknown":
            unknown.append({"id": incident["id"], "coords": incident["coords"]})
        ordered = {
            "id": incident["id"],
            "verified": incident["verified"],
            "desc": incident["desc"],
            "desc_fa": incident["desc_fa"],
            "coords": incident["coords"],
            "province": province_name,
            "link": incident["link"],
            "date": incident["date"],
            "size": incident["size"],
            "alt": incident["alt"],
        }
        updated.append(ordered)
    return updated, unknown


def parse_incidents(content, pattern):
    match = pattern.search(content)
    if not match:
        raise ValueError("Incident list not found")
    array_text = match.group(1).strip()
    if not array_text:
        return [], match
    incidents = json.loads(f"[{array_text}]")
    return incidents, match


def format_incidents(incidents, indent="                "):
    lines = [f"{indent}{json.dumps(incident, ensure_ascii=False)}" for incident in incidents]
    return "\n" + ",\n".join(lines) + "\n            "


def replace_block(content, pattern, new_block):
    match = pattern.search(content)
    if not match:
        raise ValueError("Pattern not found")
    start, end = match.span(1)
    return content[:start] + new_block + content[end:]


def main():
    content = INDEX_PATH.read_text()
    provinces = load_provinces()

    verified_incidents, _ = parse_incidents(content, VERIFIED_PATTERN)
    unverified_incidents, _ = parse_incidents(content, UNVERIFIED_PATTERN)

    updated_verified, unknown_verified = annotate_incidents(verified_incidents, provinces)
    updated_unverified, unknown_unverified = annotate_incidents(unverified_incidents, provinces)

    updated_content = replace_block(
        content,
        VERIFIED_PATTERN,
        format_incidents(updated_verified),
    )
    updated_content = replace_block(
        updated_content,
        UNVERIFIED_PATTERN,
        format_incidents(updated_unverified),
    )

    INDEX_PATH.write_text(updated_content)

    unknown = unknown_verified + unknown_unverified
    if unknown:
        print("Unknown province coordinates:")
        for entry in unknown:
            print(f"- {entry['id']}: {entry['coords']}")
    else:
        print("All incidents assigned to a province.")


if __name__ == "__main__":
    main()
