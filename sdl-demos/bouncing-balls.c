#include <SDL2/SDL.h>
#include <math.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define BALLS 32

typedef struct {
    float x, y, vx, vy, r;
    Uint8 r8, g8, b8;
} Ball;

int main(int argc, char *argv[]) {
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER);
    SDL_Window *win = SDL_CreateWindow("Bouncing Balls", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, W, H, SDL_WINDOW_FULLSCREEN);
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    
    if (SDL_NumJoysticks() > 0) SDL_GameControllerOpen(0);

    Ball balls[BALLS];
    srand(time(NULL));
    for (int i = 0; i < BALLS; i++) {
        balls[i].x = rand() % (W - 40) + 20;
        balls[i].y = rand() % (H - 40) + 20;
        balls[i].vx = (rand() % 200 - 100) / 50.0f;
        balls[i].vy = (rand() % 200 - 100) / 50.0f;
        balls[i].r = rand() % 15 + 8;
        balls[i].r8 = rand() % 255;
        balls[i].g8 = rand() % 255;
        balls[i].b8 = rand() % 255;
    }

    int running = 1;
    SDL_Event e;
    while (running) {
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) running = 0;
            if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_ESCAPE) running = 0;
            if (e.type == SDL_CONTROLLERBUTTONDOWN && e.cbutton.button == SDL_CONTROLLER_BUTTON_START) running = 0;
        }

        for (int i = 0; i < BALLS; i++) {
            balls[i].x += balls[i].vx;
            balls[i].y += balls[i].vy;
            if (balls[i].x < balls[i].r || balls[i].x > W - balls[i].r) balls[i].vx *= -1;
            if (balls[i].y < balls[i].r || balls[i].y > H - balls[i].r) balls[i].vy *= -1;
            balls[i].x = fmax(balls[i].r, fmin(W - balls[i].r, balls[i].x));
            balls[i].y = fmax(balls[i].r, fmin(H - balls[i].r, balls[i].y));
        }

        SDL_SetRenderDrawColor(ren, 20, 20, 30, 255);
        SDL_RenderClear(ren);
        for (int i = 0; i < BALLS; i++) {
            SDL_SetRenderDrawColor(ren, balls[i].r8, balls[i].g8, balls[i].b8, 255);
            // Simple circle fill
            for (int dy = -balls[i].r; dy <= balls[i].r; dy++) {
                int dx = (int)sqrt(balls[i].r * balls[i].r - dy * dy);
                SDL_Rect rect = { (int)balls[i].x - dx, (int)balls[i].y + dy, dx * 2, 1 };
                SDL_RenderFillRect(ren, &rect);
            }
        }
        SDL_RenderPresent(ren);
    }

    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
