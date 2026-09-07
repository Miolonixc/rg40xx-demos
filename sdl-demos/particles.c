#include <SDL2/SDL.h>
#include <math.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define PARTICLES 512

typedef struct {
    float x, y, vx, vy, life, maxLife;
    Uint8 r, g, b;
} Particle;

int main(int argc, char *argv[]) {
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER);
    SDL_Window *win = SDL_CreateWindow("Particles", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, W, H, SDL_WINDOW_FULLSCREEN);
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);

    SDL_GameController *ctrl = NULL;
    if (SDL_NumJoysticks() > 0) ctrl = SDL_GameControllerOpen(0);

    Particle particles[PARTICLES];
    srand(time(NULL));
    
    for (int i = 0; i < PARTICLES; i++) {
        particles[i].x = W / 2;
        particles[i].y = H / 2;
        float angle = (rand() % 360) * M_PI / 180.0f;
        float speed = rand() % 100 + 50;
        particles[i].vx = cos(angle) * speed;
        particles[i].vy = sin(angle) * speed;
        particles[i].life = 0;
        particles[i].maxLife = rand() % 100 + 50;
        particles[i].r = rand() % 255;
        particles[i].g = rand() % 255;
        particles[i].b = rand() % 255;
    }

    int running = 1, frame = 0;
    SDL_Event e;
    while (running) {
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) running = 0;
            if (e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_ESCAPE) running = 0;
            if (e.type == SDL_CONTROLLERBUTTONDOWN && e.cbutton.button == SDL_CONTROLLER_BUTTON_START) running = 0;
        }

        // Respawn dead particles
        for (int i = 0; i < PARTICLES; i++) {
            if (particles[i].life >= particles[i].maxLife) {
                particles[i].x = W / 2 + (rand() % 40 - 20);
                particles[i].y = H / 2 + (rand() % 40 - 20);
                float angle = (rand() % 360) * M_PI / 180.0f;
                float speed = rand() % 150 + 50;
                particles[i].vx = cos(angle) * speed;
                particles[i].vy = sin(angle) * speed;
                particles[i].life = 0;
                particles[i].maxLife = rand() % 80 + 40;
            }
        }

        // Update
        for (int i = 0; i < PARTICLES; i++) {
            particles[i].x += particles[i].vx * 0.016f;
            particles[i].y += particles[i].vy * 0.016f;
            particles[i].vy += 9.8f * 0.016f; // gravity
            particles[i].life += 1;
            particles[i].vx *= 0.99f;
        }

        // Render
        SDL_SetRenderDrawColor(ren, 10, 10, 20, 255);
        SDL_RenderClear(ren);
        
        for (int i = 0; i < PARTICLES; i++) {
            float alpha = 1.0f - (particles[i].life / particles[i].maxLife);
            SDL_SetRenderDrawColor(ren, particles[i].r, particles[i].g, particles[i].b, (Uint8)(alpha * 255));
            SDL_Rect rect = { (int)particles[i].x, (int)particles[i].y, 3, 3 };
            SDL_RenderFillRect(ren, &rect);
        }
        
        SDL_RenderPresent(ren);
        frame++;
    }

    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
