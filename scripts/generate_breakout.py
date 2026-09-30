import json
import os
import random
import urllib.error
import urllib.request
from pathlib import Path


GITHUB_API = "https://api.github.com/graphql"

GITHUB_USER = os.getenv("GITHUB_USER", "gahashi")

TOKEN = (
    os.getenv("PROFILE_TOKEN")
    or os.getenv("GITHUB_TOKEN")
)

OUTPUT = Path(
    os.getenv(
        "BREAKOUT_OUTPUT",
        "assets/contribution-breakout.svg"
    )
)


# ---------------------------------------------------------
# VHS / CASSETTE PALETTE
# ---------------------------------------------------------

BACKGROUND = "#1A0F0A"
PANEL = "#24120D"
EMPTY = "#2B1812"

WINE = "#5A1F1A"
RED = "#A63D2F"
ORANGE = "#D9772B"
YELLOW = "#E5B94A"
CREAM = "#F4E7C5"

MUTED = "#A98B72"


HP_COLORS = {
    1: WINE,
    2: RED,
    3: ORANGE,
    4: YELLOW,
    5: CREAM,
}


# ---------------------------------------------------------
# GITHUB
# ---------------------------------------------------------

def get_contributions():
    if not TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN não foi encontrado."
        )

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                weekday
              }
            }
          }
        }
      }
    }
    """

    payload = json.dumps({
        "query": query,
        "variables": {
            "login": GITHUB_USER
        }
    }).encode("utf-8")

    request = urllib.request.Request(
        GITHUB_API,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "gahashi-contribution-breakout",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:
            data = json.load(response)

    except urllib.error.HTTPError as error:
        body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"GitHub API retornou {error.code}: {body}"
        ) from error

    if data.get("errors"):
        raise RuntimeError(
            json.dumps(
                data["errors"],
                indent=2
            )
        )

    user = data.get("data", {}).get("user")

    if not user:
        raise RuntimeError(
            f"Usuário '{GITHUB_USER}' não encontrado."
        )

    return (
        user[
            "contributionsCollection"
        ][
            "contributionCalendar"
        ]
    )


# ---------------------------------------------------------
# CONTRIBUTION → HIT POINTS
# ---------------------------------------------------------

def get_hp(count):
    if count <= 0:
        return 0

    if count <= 2:
        return 1

    if count <= 5:
        return 2

    if count <= 9:
        return 3

    if count <= 14:
        return 4

    return 5


# ---------------------------------------------------------
# UTILS
# ---------------------------------------------------------

def fmt_number(value):
    return f"{value:,}".replace(",", ".")


def svg_number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def clamp(value, minimum, maximum):
    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


# ---------------------------------------------------------
# SVG
# ---------------------------------------------------------

def generate_svg(calendar):
    weeks = calendar["weeks"]

    total_contributions = (
        calendar["totalContributions"]
    )

    width = 1000
    height = 340

    cell = 10
    gap = 3
    pitch = cell + gap

    grid_width = (
        len(weeks) * pitch
        - gap
    )

    grid_x = (
        width - grid_width
    ) / 2

    grid_y = 88

    paddle_width = 92
    paddle_height = 8
    paddle_y = 298

    ball_radius = 5

    game_bottom = (
        paddle_y
        - ball_radius
        - 3
    )

    bricks = []
    cells = []

    active_days = 0

    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:

            count = day["contributionCount"]
            weekday = day["weekday"]

            x = (
                grid_x
                + week_index * pitch
            )

            y = (
                grid_y
                + weekday * pitch
            )

            hp = get_hp(count)

            cell_data = {
                "x": x,
                "y": y,
                "count": count,
                "hp": hp,
                "date": day["date"],
            }

            cells.append(cell_data)

            if hp > 0:
                active_days += 1
                bricks.append(cell_data)


    # -----------------------------------------------------
    # DEFINE A ORDEM DO JOGO
    # -----------------------------------------------------

    random_seed = (
        total_contributions
        + active_days * 31
    )

    rng = random.Random(
        random_seed
    )

    game_bricks = bricks.copy()

    rng.shuffle(
        game_bricks
    )


    # -----------------------------------------------------
    # TRAJETÓRIA DA BOLA
    # -----------------------------------------------------

    center_x = width / 2

    points = [
        (
            center_x,
            game_bottom
        )
    ]

    hit_indexes = {}

    for brick in game_bricks:

        brick_key = brick["date"]

        hit_indexes[
            brick_key
        ] = []

        for hit in range(
            brick["hp"]
        ):

            brick_center_x = (
                brick["x"]
                + cell / 2
            )

            brick_center_y = (
                brick["y"]
                + cell / 2
            )

            # A bola acerta o tijolo.
            points.append(
                (
                    brick_center_x,
                    brick_center_y
                )
            )

            hit_indexes[
                brick_key
            ].append(
                len(points) - 1
            )

            # Depois rebate na barra.
            offset = rng.randint(
                -135,
                135
            )

            return_x = clamp(
                brick_center_x
                + offset,
                80,
                width - 80
            )

            points.append(
                (
                    return_x,
                    game_bottom
                )
            )


    if len(points) == 1:
        points.extend([
            (
                width * 0.35,
                grid_y + 40
            ),
            (
                width * 0.65,
                game_bottom
            ),
            (
                center_x,
                game_bottom
            ),
        ])


    # Pausa no final para mostrar BUILD CLEARED.
    for _ in range(28):
        points.append(
            points[-1]
        )


    total_points = len(points)

duration = clamp(
    total_points * 0.11,
    50,
    120
)


    # -----------------------------------------------------
    # BOLA
    # -----------------------------------------------------

    ball_x_values = ";".join(
        svg_number(x)
        for x, _ in points
    )

    ball_y_values = ";".join(
        svg_number(y)
        for _, y in points
    )


    # -----------------------------------------------------
    # PADDLE
    # -----------------------------------------------------

    paddle_positions = []

    previous_x = center_x

    for x, _ in points:

        target_x = (
            previous_x
            - paddle_width / 2
        )

        target_x = clamp(
            target_x,
            20,
            width
            - paddle_width
            - 20
        )

        paddle_positions.append(
            target_x
        )

        previous_x = x


    paddle_values = ";".join(
        svg_number(x)
        for x in paddle_positions
    )


    # -----------------------------------------------------
    # SVG
    # -----------------------------------------------------

    svg = []

    svg.append(
        f'''<svg
  width="100%"
  height="{height}"
  viewBox="0 0 {width} {height}"
  xmlns="http://www.w3.org/2000/svg"
  role="img"
  aria-labelledby="title description"
>'''
    )

    svg.append(
        f"""
<title id="title">
  {GITHUB_USER} Contribution Breakout
</title>

<desc id="description">
  Jogo Breakout animado usando as contribuições reais do GitHub.
  Dias com mais contribuições precisam de mais acertos para desaparecer.
</desc>
"""
    )


    # -----------------------------------------------------
    # DEFINITIONS
    # -----------------------------------------------------

    svg.append(
        f"""
<defs>

  <linearGradient
    id="headerGradient"
    x1="0%"
    y1="0%"
    x2="100%"
    y2="0%"
  >
    <stop
      offset="0%"
      stop-color="{WINE}"
    />

    <stop
      offset="42%"
      stop-color="{RED}"
    />

    <stop
      offset="72%"
      stop-color="{ORANGE}"
    />

    <stop
      offset="100%"
      stop-color="{YELLOW}"
    />
  </linearGradient>

  <filter
    id="ballGlow"
    x="-100%"
    y="-100%"
    width="300%"
    height="300%"
  >
    <feGaussianBlur
      stdDeviation="3"
      result="blur"
    />

    <feMerge>
      <feMergeNode in="blur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>

</defs>
"""
    )


    # -----------------------------------------------------
    # BACKGROUND
    # -----------------------------------------------------

    svg.append(
        f"""
<rect
  x="1"
  y="1"
  width="{width - 2}"
  height="{height - 2}"
  rx="18"
  fill="{BACKGROUND}"
  stroke="{WINE}"
  stroke-width="2"
/>

<rect
  x="1"
  y="1"
  width="{width - 2}"
  height="5"
  rx="2"
  fill="url(#headerGradient)"
/>
"""
    )


    # -----------------------------------------------------
    # HUD
    # -----------------------------------------------------

    svg.append(
        f"""
<text
  x="28"
  y="34"
  fill="{CREAM}"
  font-family="monospace"
  font-size="16"
  font-weight="700"
  letter-spacing="1"
>
  GAHASHI // CONTRIBUTION BREAKOUT
</text>

<text
  x="28"
  y="58"
  fill="{MUTED}"
  font-family="monospace"
  font-size="12"
>
  {fmt_number(total_contributions)} CONTRIBUTIONS · {active_days} ACTIVE DAYS
</text>

<text
  x="{width - 28}"
  y="34"
  fill="{YELLOW}"
  font-family="monospace"
  font-size="12"
  text-anchor="end"
>
  AUTO PLAY
  <animate
    attributeName="fill-opacity"
    values="1;0.35;1"
    dur="1.2s"
    repeatCount="indefinite"
  />
</text>

<text
  x="{width - 28}"
  y="58"
  fill="{MUTED}"
  font-family="monospace"
  font-size="11"
  text-anchor="end"
>
  more commits = more hits
</text>
"""
    )


    # -----------------------------------------------------
    # WEEKDAY MARKERS
    # -----------------------------------------------------

    for label, row in [
        ("M", 1),
        ("W", 3),
        ("F", 5),
    ]:

        label_y = (
            grid_y
            + row * pitch
            + 8
        )

        svg.append(
            f"""
<text
  x="{grid_x - 15:.2f}"
  y="{label_y:.2f}"
  fill="{MUTED}"
  font-family="monospace"
  font-size="8"
  text-anchor="middle"
>
  {label}
</text>
"""
        )


    # -----------------------------------------------------
    # CONTRIBUTION CELLS
    # -----------------------------------------------------

    for brick in cells:

        x = brick["x"]
        y = brick["y"]
        hp = brick["hp"]
        count = brick["count"]
        date = brick["date"]

        if hp == 0:

            svg.append(
                f"""
<rect
  x="{x:.2f}"
  y="{y:.2f}"
  width="{cell}"
  height="{cell}"
  rx="2"
  fill="{EMPTY}"
  opacity="0.72"
/>
"""
            )

            continue


        hit_list = (
            hit_indexes.get(
                date,
                []
            )
        )

        animations = []


        # ---------------------------------------------
        # MUDA DE COR A CADA HIT
        # ---------------------------------------------

        if hp > 1 and hit_list:

            fill_values = [
                HP_COLORS[hp]
            ]

            fill_times = [
                0.0
            ]

            remaining_hp = hp

            for index in hit_list[:-1]:

                remaining_hp -= 1

                fraction = (
                    index
                    /
                    (
                        total_points
                        - 1
                    )
                )

                fill_times.append(
                    fraction
                )

                fill_values.append(
                    HP_COLORS[
                        max(
                            remaining_hp,
                            1
                        )
                    ]
                )


            fill_times.append(
                1.0
            )

            fill_values.append(
                fill_values[-1]
            )

            animations.append(
                f"""
  <animate
    attributeName="fill"
    values="{";".join(fill_values)}"
    keyTimes="{";".join(f"{value:.6f}" for value in fill_times)}"
    calcMode="discrete"
    dur="{duration:.2f}s"
    repeatCount="indefinite"
  />
"""
            )


        # ---------------------------------------------
        # DESAPARECE NO ÚLTIMO HIT
        # ---------------------------------------------

        if hit_list:

            final_hit = (
                hit_list[-1]
                /
                (
                    total_points
                    - 1
                )
            )

            animations.append(
                f"""
  <animate
    attributeName="opacity"
    values="1;0;0"
    keyTimes="0;{final_hit:.6f};1"
    calcMode="discrete"
    dur="{duration:.2f}s"
    repeatCount="indefinite"
  />
"""
            )


        svg.append(
            f"""
<rect
  x="{x:.2f}"
  y="{y:.2f}"
  width="{cell}"
  height="{cell}"
  rx="2"
  fill="{HP_COLORS[hp]}"
>
  <title>
    {date} · {count} contributions · {hp} hit{"s" if hp != 1 else ""}
  </title>
{"".join(animations)}</rect>
"""
        )


    # -----------------------------------------------------
    # BALL
    # -----------------------------------------------------

    svg.append(
        f"""
<circle
  cx="{center_x}"
  cy="{game_bottom}"
  r="{ball_radius}"
  fill="{CREAM}"
  filter="url(#ballGlow)"
>
  <animate
    attributeName="cx"
    values="{ball_x_values}"
    dur="{duration:.2f}s"
    repeatCount="indefinite"
    calcMode="linear"
  />

  <animate
    attributeName="cy"
    values="{ball_y_values}"
    dur="{duration:.2f}s"
    repeatCount="indefinite"
    calcMode="linear"
  />
</circle>
"""
    )


    # -----------------------------------------------------
    # PADDLE
    # -----------------------------------------------------

    svg.append(
        f"""
<rect
  x="{center_x - paddle_width / 2}"
  y="{paddle_y}"
  width="{paddle_width}"
  height="{paddle_height}"
  rx="4"
  fill="{ORANGE}"
>
  <animate
    attributeName="x"
    values="{paddle_values}"
    dur="{duration:.2f}s"
    repeatCount="indefinite"
    calcMode="linear"
  />
</rect>

<rect
  x="{center_x - 27}"
  y="{paddle_y + 2}"
  width="54"
  height="2"
  rx="1"
  fill="{YELLOW}"
>
  <animate
    attributeName="x"
    values="{";".join(svg_number(x + 19) for x in paddle_positions)}"
    dur="{duration:.2f}s"
    repeatCount="indefinite"
    calcMode="linear"
  />
</rect>
"""
    )


    # -----------------------------------------------------
    # BUILD CLEARED
    # -----------------------------------------------------

    svg.append(
        f"""
<g opacity="0">

  <text
    x="{width / 2}"
    y="228"
    fill="{CREAM}"
    font-family="monospace"
    font-size="22"
    font-weight="700"
    text-anchor="middle"
  >
    BUILD CLEARED ✓
  </text>

  <text
    x="{width / 2}"
    y="250"
    fill="{YELLOW}"
    font-family="monospace"
    font-size="11"
    text-anchor="middle"
  >
    git push origin main
  </text>

  <animate
    attributeName="opacity"
    values="0;0;1;1;0"
    keyTimes="0;0.91;0.925;0.985;1"
    calcMode="discrete"
    dur="{duration:.2f}s"
    repeatCount="indefinite"
  />

</g>
"""
    )


    # -----------------------------------------------------
    # FOOTER
    # -----------------------------------------------------

    svg.append(
        f"""
<text
  x="28"
  y="{height - 17}"
  fill="{MUTED}"
  font-family="monospace"
  font-size="10"
>
  BUILD → AUTOMATE → OPERATE
</text>

<text
  x="{width - 28}"
  y="{height - 17}"
  fill="{MUTED}"
  font-family="monospace"
  font-size="10"
  text-anchor="end"
>
  github.com/{GITHUB_USER}
</text>

</svg>
"""
    )

    return "".join(svg)


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    print(
        f"Buscando contribuições de @{GITHUB_USER}..."
    )

    calendar = get_contributions()

    svg = generate_svg(
        calendar
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        svg,
        encoding="utf-8"
    )

    print(
        f"SVG gerado em: {OUTPUT}"
    )

    print(
        "Total de contribuições:",
        calendar["totalContributions"]
    )


if __name__ == "__main__":
    main()