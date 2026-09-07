#include "raylib.h"
#include <math.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define MAX_DROPS 200

typedef struct {
    float x, y, speed, length;
} Drop;

int main(void) {
    InitWindow(W, H, "Matrix Rain");
    SetTargetFPS(60);
    bool hasPad = IsGamepadAvailable(0);

    Drop drops[MAX_DROPS];
    srand(time(NULL));
    for (int i = 0; i < MAX_DROPS; i++) {
        drops[i].x = rand() % W;
        drops[i].y = rand() % H;
        drops[i].speed = rand() % 100 / 100.0f + 0.5f;
        drops[i].length = rand() % 15 + 5;
    }

    float speedMul = 1.0f;

    while (!WindowShouldClose()) {
        if (hasPad) {
            speedMul += GetGamepadAxisMovement(0, 1) * 0.05f;
            speedMul = fmax(0.2f, fmin(3.0f, speedMul));
        }
        if (IsKeyDown(KEY_UP) || IsKeyDown(KEY_W)) speedMul += 0.05f;
        if (IsKeyDown(KEY_DOWN) || IsKeyDown(KEY_S)) speedMul -= 0.05f;
        speedMul = fmax(0.2f, fmin(3.0f, speedMul));

        BeginDrawing();
        ClearBackground(BLACK);

        for (int i = 0; i < MAX_DROPS; i++) {
            drops[i].y += drops[i].speed * speedMul * 2;
            if (drops[i].y > H) {
                drops[i].y = -drops[i].length * 20;
                drops[i].x = rand() % W;
            }

            for (int j = 0; j < drops[i].length; j++) {
                int alpha = 255 - (j * 255 / drops[i].length);
                Color c = { 0, (unsigned char)(alpha * 0.7f), 0, (unsigned char)alpha };
                if (j == 0) c = RAYWHITE;
                DrawText(TextFormat("%c", rand() % 96 + 32), 
                         (int)drops[i].x, (int)drops[i].y - j * 20, 18, c);
            }
        }

        DrawText(TextFormat("Speed: %.1fx", speedMul), 10, 10, 20, DARKGREEN);
        DrawFPS(W - 80, 10);
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
