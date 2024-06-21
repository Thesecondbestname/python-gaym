from abc import ABC, abstractmethod
import pygame
from random import randint
import math
from typing import Tuple, TypeVar, List
from pygame._sdl2 import Window
import sys

pygame.init()
T = TypeVar("T", bound=int | float)


class Vec(tuple[T, T]):
    def __add__(self, other):
        return Vec[T](x + y for x, y in zip(self, other))

    def __sub__(self, other):
        return Vec[T](x - y for x, y in zip(self, other))

    def __mul__(self, other):
        return Vec[T](x * y for x, y in zip(self, other))

    def __rmul__(self, other):
        return Vec(other * x for x in self)

    def tup(self) -> Tuple[T, T]:
        return (self[0], self[1])

    def fold(self, f):
        return f(self[0], self[1])

    def fmap(self, f):
        return Vec((f(self[0], self[1])))


BOTTOM = pygame.display.Info().current_h
RIGHT = pygame.display.Info().current_w
TOP = 0
LEFT = 0
WINDOW_WIDTH = RIGHT / 5
WINDOW_HEIGHT = BOTTOM / 5
DRAG = 0.95
SPIN_SPEED = 1
SPEED = 5
INFO_COLOR = (205, 214, 244)
BAD_COLOR = (243, 139, 168)
GOOD_COLOR = (166, 227, 161)
POINT_COLOR = (250, 179, 135)


class ProjectileInterface(ABC):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (
            hasattr(subclass, "moving_outside_view")
            and callable(subclass.moving_outside_view)
            and hasattr(subclass, "update_positions")
            and callable(subclass.update_positions)
            and hasattr(subclass, "check_collision_with_point")
            and callable(subclass.check_collision_with_point)
            and hasattr(subclass, "draw")
            and callable(subclass.draw)
            or NotImplemented
        )

    @abstractmethod
    def moving_outside_view(self) -> bool:
        """Remove projectiles that are out of view and check if entire projectile is out of view"""
        raise NotImplementedError

    @abstractmethod
    def update_positions(self) -> None:
        """Update positions of individual thingamajigs in the projectiles"""
        raise NotImplementedError

    @abstractmethod
    def draw(self, screen: pygame.Surface, pos: Vec[float]) -> None:
        """Draw the projectile to the screen"""
        raise NotImplementedError

    @abstractmethod
    def check_collision_with_point(self, pos: Vec[float], size: int) -> bool:
        """Check if any of the projectiles collide with player"""
        raise NotImplementedError


class Sinusoiod(ProjectileInterface):
    def __init__(
        self,
        pos: Tuple[float, float],
        size: float,
        vel: Vec[int],
        group_amnt: int,  # Python hat keine enums?!
    ):
        self.size, self.vel = size, vel
        stretchedlen = math.hypot(vel[0], vel[1]) * self.size * 3
        self.center = Vec(pos)
        self.pos: List[Vec[float]] = []
        self.angle: float = 1
        for i in range(0, group_amnt):
            self.pos.append(
                Vec(self.center + self.vel * Vec((stretchedlen * i, stretchedlen * i)))
            )
        self.col = BAD_COLOR

    def draw(self, screen, pos) -> None:
        [
            pygame.draw.circle(screen, self.col, (opos - pos).tup(), self.size)
            for opos in self.pos
        ]

    def update_positions(self) -> None:
        self.pos = [obj + self.vel for obj in self.pos]
        self.angle += 1

    def check_collision_with_point(self, a_pos, size) -> bool:
        acc = False
        [acc:= acc or circle_touches(
                    size,
                    self.size,
                    a_pos,
                    pos,
                ) for pos in self.pos]
        return acc

    def moving_outside_view(self) -> bool:
        for pos in self.pos:
            if pos[0] < LEFT or pos[0] > RIGHT or pos[1] < TOP or pos[1] > BOTTOM:
                normallen = 1 / math.hypot(self.vel[0], self.vel[1])
                normalvec = pos * Vec((normallen, normallen))
                dotprod = normalvec * Vec((BOTTOM // 2, RIGHT // 2))
                if dotprod[0] + dotprod[1] > 0:
                    print(f"removing{pos}")
                    self.pos.remove(pos)
        return len(self.pos) == 0


class Circle(ProjectileInterface):
    def __init__(
        self, pos: Tuple[float, float], size: float, vel: Vec[int], group_amnt: int
    ):
        self.size: float = size
        self.center = Vec(pos)
        self.vel: Vec[int] = vel
        self.pos: List[Tuple[Vec[float], int]] = []
        self.amnt = group_amnt
        self.angle: float = 1
        self.radius = (self.amnt + 1) * self.size
        circlePart = 2 * math.pi / self.amnt
        for i in range(1, self.amnt + 1):
            offset = i * circlePart + circlePart / 2
            x = self.radius * math.cos(offset)
            y = self.radius * math.sin(offset)
            self.pos.append((self.center + Vec((x, y)), i))
        self.col = BAD_COLOR

    def draw(self, screen, pos):
        [
            pygame.draw.circle(screen, self.col, (opos - pos).tup(), self.size)
            for opos, i in self.pos
        ]

    def check_collision_with_point(self, a_pos, size) -> bool:
        acc = False
        [acc:= acc or circle_touches(
                    size,
                    self.size,
                    a_pos,
                    pos,
                ) for pos,i in self.pos]
        return acc

    def update_positions(self):
        circlePart = 2 * math.pi / self.amnt
        pos = []
        for obj, i in self.pos:
            offset = i * circlePart + circlePart / 2
            x = self.radius * math.cos(math.radians(self.angle) + offset)
            y = self.radius * math.sin(math.radians(self.angle) + offset)
            pos.append((self.center + Vec((x, y)), i))
        self.pos = pos
        self.center += self.vel
        self.angle = self.angle + SPIN_SPEED if self.angle < 360 else 0

    def moving_outside_view(self) -> bool:
        for ipos in self.pos:
            pos, i = ipos
            if (
                pos[0] + self.size < LEFT
                or pos[0] - self.size > RIGHT
                or pos[1] - self.size < TOP
                or pos[1] + self.size > BOTTOM
            ):
                if (
                    (self.center)[0] < LEFT
                    or (self.center)[0] > RIGHT
                    or (self.center)[1] < TOP
                    or (self.center)[1] > BOTTOM
                ):
                    print(f"removing {pos}")
                    self.pos.remove(ipos)
        return len(self.pos) == 0


def solve_window_collisions(pos: Vec, vel: Vec) -> Tuple[Vec, Vec]:
    velx, vely = vel.tup()
    x, y = pos.tup()
    if x < LEFT:
        velx = -1.3 * velx
        x = LEFT
    if x > RIGHT - WINDOW_WIDTH:
        velx = -1.3 * velx
        x = RIGHT - WINDOW_WIDTH
    if y < TOP:
        vely = -1.3 * vely
        y = TOP
    if y > BOTTOM - WINDOW_HEIGHT:
        vely = -1.3 * vely
        y = BOTTOM - WINDOW_HEIGHT
    return (Vec((x, y)), Vec((velx, vely)))


def update_velocity(vel: Vec) -> Vec:
    inp_vel = Vec(
        (
            pygame.key.get_pressed()[pygame.K_d]
            + pygame.key.get_pressed()[pygame.K_a] * -1.0,
            pygame.key.get_pressed()[pygame.K_s]
            + pygame.key.get_pressed()[pygame.K_w] * -1.0,
        )
    ) * Vec((SPEED * 0.1, SPEED * 0.1))
    return (inp_vel + vel) * Vec((DRAG, DRAG))


def intro(screen: pygame.Surface, text_font) -> None:
    screen.fill((34, 34, 64))
    screen.blit(render_text("Whuacamole", text_font), (0, WINDOW_HEIGHT // 5))
    screen.blit(render_text("WASD zum bwegen", text_font), (0, 2 * WINDOW_HEIGHT // 5))
    screen.blit(
        render_text("Leertaste zum startn", text_font), (0, 3 * WINDOW_HEIGHT // 5)
    )
    pygame.display.flip()


def main() -> None:
    # instantiate environment constants
    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT), pygame.NOFRAME | pygame.RESIZABLE
    )
    window = Window.from_display_module()
    text_font = pygame.font.SysFont("", int(WINDOW_HEIGHT // 5))
    clock = pygame.time.Clock()
    # global TOP, LEFT
    # LEFT, TOP = calculate_top_left_offset(window, screen)

    # instantiate game variables
    vel: Vec[float] = Vec((5, 5))
    pos: Vec[int] = Vec(window.position)
    c_size: int = int(WINDOW_WIDTH / 15)
    p_size = c_size 
    tick, points, growing, point = 0, 0, False, newpoint(p_size)

    # create projectiles
    projectiles: List[ProjectileInterface] = [
        Sinusoiod((RIGHT / 4, BOTTOM / 4), size=20, vel=Vec((1, 1)), group_amnt=6),
        Circle((RIGHT / 2, BOTTOM / 2), size=30, vel=Vec((0, 1)), group_amnt=5),
    ]

    while not len(pygame.event.get(pygame.KEYDOWN)):
        intro(screen, text_font)

    while True:
        # update game state
        tick += 1
        clock.tick(60)
        vel = update_velocity(vel)
        pos, vel = solve_window_collisions(pos, vel)
        pos += vel
        window.position = pos.tup()

        # draw everything to da screen
        screen.fill((34, 34, 64))
        screen.blit(
            render_text(f"{points}", text_font),
            (WINDOW_WIDTH // 10, WINDOW_HEIGHT // 10),
        )
        pygame.draw.circle(
            screen, GOOD_COLOR, (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2), c_size
        )
        pygame.draw.circle(screen, POINT_COLOR, point - window.position, p_size)
        for pro in projectiles:
            pro.update_positions()
            if pro.moving_outside_view():
                projectiles.remove(pro)
            pro.draw(screen, Vec(window.position))

        # getting points logic
        if circle_touches(
            c_size,
            0,
            Vec((WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)),
            point - window.position,
        ):
            point = newpoint(p_size)
            points += 1
            c_size = int(WINDOW_WIDTH // 15)
            growing = False

        if tick % 60 == 0:
            projectiles.append(new_projectile(p_size, window.position))

        if growing:
            c_size += 7
            if c_size > WINDOW_WIDTH / 2:
                c_size = int(WINDOW_WIDTH // 15)
                growing = False

        # update game for events
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                key = pygame.key.name(event.key)
                if key == "space":
                    growing = True
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        pygame.display.flip()


def newpoint(size: int) -> Vec[int]:
    x_border = RIGHT//10
    y_border = BOTTOM//10
    return Vec((randint(x_border, RIGHT - (LEFT+y_border)), randint(x_border, BOTTOM - (TOP + y_border))))

def new_projectile(size: float, win_pos: Tuple[int, int]):
    kind = randint(0,1)
    x,y = randint(1,10),randint(1,10)
    while (Vec((RIGHT / x, BOTTOM / y)) - Vec(win_pos)).fold(lambda x,y: math.hypot(x,y)) < WINDOW_WIDTH: 
        x,y = randint(1,10),randint(1,10)
    size = size + randint(0,5)
    amnt = randint(3,6)
    velx,vely = randint(-4,3),randint(-4,3)
    if velx ==0: velx = 1
    if vely ==0: vely = 1
    if kind ==0: return Sinusoiod((RIGHT / x, BOTTOM / y), size=size, vel=Vec((velx, vely)), group_amnt=amnt)
    if kind ==1: return Circle((RIGHT / x, BOTTOM / y), size=size, vel=Vec((velx, vely)), group_amnt=amnt)

def calculate_top_left_offset(window: Window, screen) -> Tuple[int, int]:
    window.maximize()
    x, y = screen.get_size()
    dim = (abs(RIGHT - x), abs(BOTTOM - y))
    window.restore()
    return dim


def sin(x: float) -> float:
    return math.sin(math.radians(x))


def cos(x: float) -> float:
    return math.cos(math.radians(x))


def render_text(text: str, font):
    return font.render(text, True, INFO_COLOR)


def circle_touches(radius: float,radius2: float, pos1: Vec[float], pos2: Vec[float]) -> bool:
    centered = pos2 - pos1
    dist_len = math.hypot(centered[0], centered[1])
    return dist_len - (radius + radius2) < 0


main()
