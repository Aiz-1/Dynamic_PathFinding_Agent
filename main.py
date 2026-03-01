import pygame
import random
import math
from queue import PriorityQueue
import time
import threading

pygame.init()

BACKGROUND    = "#0d1117"
OBSTACLE      = "#e05c5c"
VISITED       = "#3b82f6"
SOURCE        = "#facc15"
TARGET        = "#10b981"
ROUTE         = "#c084fc"
LINES         = "#2d2d2d"
FLASH         = "#f0f0f0"

ALGORITHM = "A_STAR"
# ALGORITHM = "GREEDY"

HEURISTIC = "MANHATTAN"
# HEURISTIC = "EUCLIDEAN"
# HEURISTIC = "DIAGONAL"


class Cell:
    def __init__(self, r, c, size, total):
        self.r      = r
        self.c      = c
        self.px     = r * size
        self.py     = c * size
        self.shade  = BACKGROUND
        self.edges  = []
        self.size   = size
        self.total  = total

    def coords(self):         return self.r, self.c
    def blocked(self):        return self.shade == OBSTACLE
    def is_src(self):         return self.shade == SOURCE
    def is_tgt(self):         return self.shade == TARGET
    def clear(self):          self.shade = BACKGROUND
    def set_src(self):        self.shade = SOURCE
    def set_visited(self):    self.shade = VISITED
    def set_open(self):       self.shade = VISITED
    def set_wall(self):       self.shade = OBSTACLE
    def set_tgt(self):        self.shade = TARGET
    def set_flash(self):      self.shade = FLASH

    def set_route(self):
        if not self.is_src() and not self.is_tgt():
            self.shade = ROUTE

    def render(self, surface):
        pygame.draw.rect(surface, self.shade, (self.px, self.py, self.size, self.size))

    def refresh_edges(self, board):
        self.edges = []
        if self.r < self.total - 1 and not board[self.r+1][self.c].blocked():
            self.edges.append(board[self.r+1][self.c])
        if self.r > 0 and not board[self.r-1][self.c].blocked():
            self.edges.append(board[self.r-1][self.c])
        if self.c < self.total - 1 and not board[self.r][self.c+1].blocked():
            self.edges.append(board[self.r][self.c+1])
        if self.c > 0 and not board[self.r][self.c-1].blocked():
            self.edges.append(board[self.r][self.c-1])


def calc_dist(a, b):
    x1, y1 = a
    x2, y2 = b
    if HEURISTIC == "MANHATTAN":  return abs(x1-x2) + abs(y1-y2)
    if HEURISTIC == "EUCLIDEAN":  return math.sqrt((x1-x2)**2 + (y1-y2)**2)
    if HEURISTIC == "DIAGONAL":   return max(abs(x1-x2), abs(y1-y2))
    return abs(x1-x2) + abs(y1-y2)


def build_board(n, w):
    step = w // n
    return [[Cell(i, j, step, n) for j in range(n)] for i in range(n)]


def draw_lines(surface, n, w):
    step = w // n
    for i in range(n):
        pygame.draw.line(surface, LINES, (0, i*step), (w, i*step))
        for j in range(n):
            pygame.draw.line(surface, LINES, (j*step, 0), (j*step, w))


def render_frame(surface, board, n, w, stats, msg):
    surface.fill(BACKGROUND)
    for row in board:
        for cell in row:
            cell.render(surface)
    draw_lines(surface, n, w)

    fnt = pygame.font.Font(None, 20)
    y = 10
    surface.blit(fnt.render(f"Mode: {ALGORITHM}",     True, OBSTACLE), (w+10, y)); y += 20
    surface.blit(fnt.render(f"Metric: {HEURISTIC}", True, OBSTACLE), (w+10, y))

    y = 60
    for k, v in stats.items():
        surface.blit(fnt.render(f"{k}: {v}", True, OBSTACLE), (w+10, y)); y += 20

    surface.blit(fnt.render(f"Status: {msg}", True, OBSTACLE), (w+10, y+10))

    y += 45
    for ln in ["Keys:", "SPACE: Run", "R: Reset"]:
        surface.blit(fnt.render(ln, True, OBSTACLE), (w+10, y)); y += 18

    pygame.display.update()


def scatter_walls(board, n, src, tgt):
    sp, tp = src.coords(), tgt.coords()
    for i in range(n):
        for j in range(n):
            cell = board[i][j]
            if (i, j) == sp or (i, j) == tp:
                continue
            if random.random() < 0.28:
                cell.set_wall()
            else:
                cell.clear()
    src.set_src()
    tgt.set_tgt()


def live_spawn(board, n, src, tgt, halt, delay=0.3):
    while not halt.is_set():
        time.sleep(delay)
        if halt.is_set():
            break
        sp, tp = src.coords(), tgt.coords()
        pool = [
            board[i][j]
            for i in range(n) for j in range(n)
            if board[i][j].shade == BACKGROUND
            and (i,j) != sp and (i,j) != tp
        ]
        if not pool:
            continue
        chosen = random.sample(pool, min(random.randint(1, 3), len(pool)))
        for cell in chosen:
            cell.set_flash()
        time.sleep(0.06)
        for cell in chosen:
            if cell.shade == FLASH:
                cell.set_wall()
                cell.refresh_edges(board)
                for nb in cell.edges:
                    nb.refresh_edges(board)


def reset_colors(board):
    for row in board:
        for cell in row:
            if cell.shade in (VISITED, ROUTE):
                cell.clear()


def trace_path(prev, cur, draw_fn, tgt):
    length = 0
    while cur in prev:
        cur = prev[cur]
        if not cur.is_src() and cur != tgt:
            cur.set_route()
        length += 1
        draw_fn()
    return length


def run_astar(draw_fn, board, src, tgt):
    ctr = 0
    heap = PriorityQueue()
    heap.put((0, ctr, src))
    prev = {}
    g = {cell: float("inf") for row in board for cell in row}
    g[src] = 0
    f = {cell: float("inf") for row in board for cell in row}
    f[src] = calc_dist(src.coords(), tgt.coords())
    open_hash = {src}
    visited = 0

    while not heap.empty():
        cur = heap.get()[2]
        open_hash.discard(cur)

        if cur == tgt:
            plen = trace_path(prev, tgt, draw_fn, tgt)
            tgt.set_tgt()
            return visited, plen, True

        for nb in cur.edges:
            if nb.blocked():
                continue
            ng = g[cur] + 1
            if ng < g[nb]:
                prev[nb] = cur
                g[nb]    = ng
                f[nb]    = ng + calc_dist(nb.coords(), tgt.coords())
                if nb not in open_hash:
                    ctr += 1; visited += 1
                    heap.put((f[nb], ctr, nb))
                    open_hash.add(nb)
                    if nb != tgt:
                        nb.set_open()
        draw_fn()
        if cur != src and cur != tgt:
            cur.set_visited()

    return visited, None, False


def run_greedy(draw_fn, board, src, tgt):
    ctr = 0
    heap = PriorityQueue()
    heap.put((0, ctr, src))
    prev      = {}
    open_hash = {src}
    visited   = 0

    while not heap.empty():
        cur = heap.get()[2]
        open_hash.discard(cur)

        if cur == tgt:
            plen = trace_path(prev, tgt, draw_fn, tgt)
            tgt.set_tgt()
            return visited, plen, True

        for nb in cur.edges:
            if nb.blocked():
                continue
            if nb not in prev and nb != src:
                prev[nb] = cur
                ctr += 1; visited += 1
                heap.put((calc_dist(nb.coords(), tgt.coords()), ctr, nb))
                open_hash.add(nb)
                if nb != tgt:
                    nb.set_open()
        draw_fn()
        if cur != src and cur != tgt:
            cur.set_visited()

    return visited, None, False


def launch(surface, canvas_w):
    N     = 15
    board = build_board(N, canvas_w)

    src = board[0][0]
    tgt = board[N-1][N-1]
    src.set_src()
    tgt.set_tgt()

    stats  = {"Cells Visited": 0, "Route Length": 0, "Time (ms)": 0}
    done   = False
    status = "Ready"

    scatter_walls(board, N, src, tgt)

    active = True
    while active:
        render_frame(surface, board, N, canvas_w, stats, status)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                active = False

            if ev.type == pygame.KEYDOWN:

                if ev.key == pygame.K_SPACE and not done:
                    for row in board:
                        for cell in row:
                            cell.refresh_edges(board)
                    reset_colors(board)
                    src.set_src()
                    tgt.set_tgt()
                    status = "Running..."
                    render_frame(surface, board, N, canvas_w, stats, status)

                    halt_flag   = threading.Event()
                    wall_thread = threading.Thread(
                        target=live_spawn,
                        args=(board, N, src, tgt, halt_flag, 0.3),
                        daemon=True
                    )
                    wall_thread.start()

                    t0 = time.time()
                    if ALGORITHM == "A_STAR":
                        nv, pc, found = run_astar(
                            lambda: render_frame(surface, board, N, canvas_w, stats, status),
                            board, src, tgt
                        )
                    else:
                        nv, pc, found = run_greedy(
                            lambda: render_frame(surface, board, N, canvas_w, stats, status),
                            board, src, tgt
                        )

                    halt_flag.set()
                    wall_thread.join(timeout=1)

                    ms = (time.time() - t0) * 1000
                    if found:
                        stats  = {"Cells Visited": nv, "Route Length": pc,
                                  "Time (ms)": round(ms, 2)}
                        status = "Route Found!"
                        done   = True
                    else:
                        status = "No Route Exists!"

                elif ev.key == pygame.K_r:
                    board = build_board(N, canvas_w)
                    src   = board[0][0]
                    tgt   = board[N-1][N-1]
                    src.set_src()
                    tgt.set_tgt()
                    done   = False
                    stats  = {"Cells Visited": 0, "Route Length": 0, "Time (ms)": 0}
                    status = "Ready"
                    scatter_walls(board, N, src, tgt)

    pygame.quit()


if __name__ == "__main__":
    SIZE   = 600
    screen = pygame.display.set_mode((SIZE + 200, SIZE))
    pygame.display.set_caption("Grid Pathfinder")
    launch(screen, SIZE)