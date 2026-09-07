#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480

typedef struct {
    float x, y, vx, vy, r;
    int r_col, g_col, b_col;
} Ball;

int main(int argc, char *argv[]) {
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER);
    SDL_Window *win = SDL_CreateWindow("Bouncing Balls", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, W, H, SDL_WINDOW_FULLSCREEN);
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_SOFTWARE);
    
    if (SDL_NumJoysticks() > 0) SDL_GameControllerOpen(0);

    Ball balls[24];
    srand(time(NULL));
    for (int i = 0; i < 24; i++) {
        balls[i].x = rand() % (W - 40) + 20;
        balls[i].y = rand() % (H - 40) + 20;
        balls[i].vx = (rand() % 200 - 100) / 40.0f;
        balls[i].vy = (rand() % 200 - 100) / 40.0f;
        balls[i].r = rand() % 12 + 6;
        balls[i].r_col = rand() % 255;
        balls[i].g_col = rand() % 255;
        balls[i].b_col = rand() % 255;
    }

    int running = 1, frame = 0;
    SDL_Event e;
    
    while (running) {
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) running = 0;
            if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_ESCAPE) running = 0;
            if (e.type == SDL_CONTROLLERBUTTONDOWN && e.cbutton.button == SDL_CONTROLLER_BUTTON_START) running = 0;
        }

        for (int i = 0; i < 24; i++) {
            balls[i].x += balls[i].vx;
            balls[i].y += balls[i].vy;
            if (balls[i].x < balls[i].r || balls[i].x > W - balls[i].r) balls[i].vx *= -1;
            if (balls[i].y < balls[i].r || balls[i].y > H - balls[i].r) balls[i].vy *= -1;
            balls[i].x = fmax(balls[i].r, fmin(W - balls[i].r, balls[i].x));
            balls[i].y = fmax(balls[i].r, fmin(H - balls[i].r, balls[i].y));
        }

        SDL_SetRenderDrawColor(ren, 15, 15, 25, 255);
        SDL_RenderClear(ren);
        
        for (int i = 0; i < 24; i++) {
            SDL_SetRenderDrawColor(ren, balls[i].r_col, balls[i].g_col, balls[i].b_col, 255);
            for (int dy = -balls[i].r; dy <= balls[i].r; dy++) {
                int dx = (int)sqrt(balls[i].r * balls[i].r - dy * dy);
                SDL_Rect rect = { (int)balls[i].x - dx, (int)balls[i].y + dy, dx * 2, 1 };
                SDL_RenderFillRect(ren, &rect);
            }
        }
        
        SDL_RenderPresent(ren);
        SDL_Delay(16);
        frame++;
    }

    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
