#include <SDL2/SDL.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define STARS 400

typedef struct {
    float x, y, z;
} Star;

int main(int argc, char *argv[]) {
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER);
    SDL_Window *win = SDL_CreateWindow("Starfield", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, W, H, SDL_WINDOW_FULLSCREEN);
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);

    if (SDL_NumJoysticks() > 0) SDL_GameControllerOpen(0);

    Star stars[STARS];
    srand(time(NULL));
    for (int i = 0; i < STARS; i++) {
        stars[i].x = rand() % W - W / 2;
        stars[i].y = rand() % H - H / 2;
        stars[i].z = rand() % W;
    }

    int running = 1;
    SDL_Event e;
    while (running) {
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) running = 0;
            if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_ESCAPE) running = 0;
            if (e.type == SDL_CONTROLLERBUTTONDOWN && e.cbutton.button == SDL_CONTROLLER_BUTTON_START) running = 0;
        }

        SDL_SetRenderDrawColor(ren, 0, 0, 0, 255);
        SDL_RenderClear(ren);

        for (int i = 0; i < STARS; i++) {
            stars[i].z -= 8;
            if (stars[i].z <= 0) {
                stars[i].x = rand() % W - W / 2;
                stars[i].y = rand() % H - H / 2;
                stars[i].z = W;
            }

            int sx = (int)(stars[i].x / stars[i].z * 200 + W / 2);
            int sy = (int)(stars[i].y / stars[i].z * 200 + H / 2);
            float size = (1.0f - stars[i].z / W) * 4;

            if (sx >= 0 && sx < W && sy >= 0 && sy < H) {
                Uint8 c = (Uint8)(255 * (1.0f - stars[i].z / W));
                SDL_SetRenderDrawColor(ren, c, c, c, 255);
                SDL_Rect r = { sx, sy, (int)size + 1, (int)size + 1 };
                SDL_RenderFillRect(ren, &r);
            }
        }

        SDL_RenderPresent(ren);
    }

    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
