#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define W 640
#define H 480
#define CELL 20
#define GRID_W (W / CELL)
#define GRID_H (H / CELL)
#define MAX_LEN 512

typedef struct { int x, y; } Point;

typedef struct {
    Point body[MAX_LEN];
    int len;
    int dirX, dirY;
    int nextDirX, nextDirY;
    int score;
    int gameOver;
    int paused;
} Game;

Point food;

void resetGame(Game *g) {
    g->len = 4;
    g->dirX = 1; g->dirY = 0;
    g->nextDirX = 1; g->nextDirY = 0;
    g->score = 0;
    g->gameOver = 0;
    g->paused = 0;
    for (int i = 0; i < g->len; i++) {
        g->body[i].x = GRID_W / 2 - i;
        g->body[i].y = GRID_H / 2;
    }
    g->body[0].x = GRID_W / 2;
    g->body[0].y = GRID_H / 2;
}

void spawnFood(Game *g) {
    int valid = 0;
    while (!valid) {
        food.x = rand() % GRID_W;
        food.y = rand() % GRID_H;
        valid = 1;
        for (int i = 0; i < g->len; i++) {
            if (g->body[i].x == food.x && g->body[i].y == food.y) {
                valid = 0;
                break;
            }
        }
    }
}

void update(Game *g) {
    if (g->gameOver || g->paused) return;
    
    g->dirX = g->nextDirX;
    g->dirY = g->nextDirY;
    
    // Move body
    for (int i = g->len - 1; i > 0; i--) {
        g->body[i] = g->body[i - 1];
    }
    g->body[0].x += g->dirX;
    g->body[0].y += g->dirY;
    
    // Wrap around
    if (g->body[0].x < 0) g->body[0].x = GRID_W - 1;
    if (g->body[0].x >= GRID_W) g->body[0].x = 0;
    if (g->body[0].y < 0) g->body[0].y = GRID_H - 1;
    if (g->body[0].y >= GRID_H) g->body[0].y = 0;
    
    // Self collision
    for (int i = 1; i < g->len; i++) {
        if (g->body[0].x == g->body[i].x && g->body[0].y == g->body[i].y) {
            g->gameOver = 1;
            return;
        }
    }
    
    // Eat food
    if (g->body[0].x == food.x && g->body[0].y == food.y) {
        if (g->len < MAX_LEN) g->len++;
        g->score += 10;
        spawnFood(g);
    }
}

void draw(SDL_Renderer *ren, Game *g) {
    SDL_SetRenderDrawColor(ren, 10, 10, 15, 255);
    SDL_RenderClear(ren);
    
    // Draw grid (subtle)
    SDL_SetRenderDrawColor(ren, 25, 25, 35, 255);
    for (int x = 0; x < GRID_W; x++) {
        for (int y = 0; y < GRID_H; y++) {
            SDL_Rect r = { x * CELL, y * CELL, CELL - 1, CELL - 1 };
            SDL_RenderDrawRect(ren, &r);
        }
    }
    
    // Draw food
    SDL_SetRenderDrawColor(ren, 255, 50, 50, 255);
    SDL_Rect fr = { food.x * CELL + 2, food.y * CELL + 2, CELL - 4, CELL - 4 };
    SDL_RenderFillRect(ren, &fr);
    
    // Draw snake
    for (int i = 0; i < g->len; i++) {
        Uint8 c = i == 0 ? 0 : 100 - (i * 150 / g->len);
        SDL_SetRenderDrawColor(ren, 0, 200 - c, 0, 255);
        SDL_Rect r = { g->body[i].x * CELL + 1, g->body[i].y * CELL + 1, CELL - 2, CELL - 2 };
        SDL_RenderFillRect(ren, &r);
    }
    
    // Draw score
    // (no text rendering without ttf, just rectangles)
    SDL_SetRenderDrawColor(ren, 255, 255, 255, 255);
    for (int i = 0; i < g->score / 10 && i < 50; i++) {
        SDL_Rect r = { 10 + i * 12, 10, 10, 10 };
        SDL_RenderFillRect(ren, &r);
    }
    
    if (g->gameOver) {
        SDL_SetRenderDrawColor(ren, 255, 0, 0, 200);
        SDL_Rect r = { W / 2 - 120, H / 2 - 30, 240, 60 };
        SDL_RenderFillRect(ren, &r);
    }
    
    if (g->paused) {
        SDL_SetRenderDrawColor(ren, 100, 100, 200, 200);
        SDL_Rect r = { W / 2 - 80, H / 2 - 20, 160, 40 };
        SDL_RenderFillRect(ren, &r);
    }
    
    SDL_RenderPresent(ren);
}

int main(int argc, char *argv[]) {
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER);
    
    SDL_Window *win = SDL_CreateWindow("Snake",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        W, H, SDL_WINDOW_FULLSCREEN);
    
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_SOFTWARE);
    
    SDL_GameController *ctrl = NULL;
    if (SDL_NumJoysticks() > 0) ctrl = SDL_GameControllerOpen(0);
    
    srand(time(NULL));
    
    Game g;
    resetGame(&g);
    spawnFood(&g);
    
    Uint32 lastUpdate = 0;
    int running = 1;
    SDL_Event e;
    
    while (running) {
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) running = 0;
            if (e.type == SDL_KEYDOWN) {
                switch (e.key.keysym.sym) {
                    case SDLK_ESCAPE: running = 0; break;
                    case SDLK_UP: if (g.dirY != 1) { g.nextDirX = 0; g.nextDirY = -1; } break;
                    case SDLK_DOWN: if (g.dirY != -1) { g.nextDirX = 0; g.nextDirY = 1; } break;
                    case SDLK_LEFT: if (g.dirX != 1) { g.nextDirX = -1; g.nextDirY = 0; } break;
                    case SDLK_RIGHT: if (g.dirX != -1) { g.nextDirX = 1; g.nextDirY = 0; } break;
                    case SDLK_p: g.paused = !g.paused; break;
                    case SDLK_r: if (g.gameOver) { resetGame(&g); spawnFood(&g); } break;
                }
            }
            if (e.type == SDL_CONTROLLERBUTTONDOWN) {
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_DPAD_UP && g.dirY != 1) { g.nextDirX = 0; g.nextDirY = -1; }
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_DPAD_DOWN && g.dirY != -1) { g.nextDirX = 0; g.nextDirY = 1; }
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_DPAD_LEFT && g.dirX != 1) { g.nextDirX = -1; g.nextDirY = 0; }
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_DPAD_RIGHT && g.dirX != -1) { g.nextDirX = 1; g.nextDirY = 0; }
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_START) g.paused = !g.paused;
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_A && g.gameOver) { resetGame(&g); spawnFood(&g); }
            }
        }
        
        Uint32 now = SDL_GetTicks();
        if (now - lastUpdate > 100) {
            update(&g);
            lastUpdate = now;
        }
        
        draw(ren, &g);
        SDL_Delay(16);
    }
    
    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
