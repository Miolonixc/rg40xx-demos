#include "raylib.h"
#include <math.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define PLAYER_W 24
#define PLAYER_H 32
#define GRAVITY 0.5
#define JUMP_FORCE -10
#define MOVE_SPEED 4
#define MAX_PLATFORMS 12
#define MAX_COINS 10

typedef struct { float x, y, w, h; Color color; } Platform;
typedef struct { float x, y, collected; } Coin;

int main(void) {
    InitWindow(W, H, "Platformer");
    SetTargetFPS(60);
    bool hasPad = IsGamepadAvailable(0);

    srand(time(NULL));

    // Generate platforms
    Platform platforms[MAX_PLATFORMS];
    platforms[0] = (Platform){ 0, H - 40, W, 40, DARKGREEN }; // ground
    for (int i = 1; i < MAX_PLATFORMS; i++) {
        platforms[i] = (Platform){
            rand() % (W - 100), rand() % (H - 150) + 80,
            rand() % 80 + 60, 15,
            (Color){ rand() % 100 + 100, rand() % 100 + 100, rand() % 100 + 100, 255 }
        };
    }

    // Generate coins
    Coin coins[MAX_COINS];
    for (int i = 0; i < MAX_COINS; i++) {
        coins[i] = (Coin){ rand() % (W - 20), rand() % (H - 200) + 50, false };
    }

    float px = W / 2, py = H - 100;
    float vx = 0, vy = 0;
    bool onGround = false;
    int score = 0;
    int frame = 0;

    while (!WindowShouldClose()) {
        // Input
        float ax = hasPad ? GetGamepadAxisMovement(0, 0) : 0;
        if (IsKeyDown(KEY_LEFT) || IsKeyDown(KEY_A) || ax < -0.3f) { vx = -MOVE_SPEED; }
        else if (IsKeyDown(KEY_RIGHT) || IsKeyDown(KEY_D) || ax > 0.3f) { vx = MOVE_SPEED; }
        else { vx = 0; }

        if ((IsKeyPressed(KEY_SPACE) || IsKeyPressed(KEY_UP) || IsKeyPressed(KEY_W) || IsKeyPressed(KEY_Z) ||
             (hasPad && IsGamepadButtonPressed(0, 0))) && onGround) {
            vy = JUMP_FORCE;
            onGround = false;
        }

        // Physics
        vy += GRAVITY;
        px += vx;
        py += vy;

        // Platform collision
        onGround = false;
        for (int i = 0; i < MAX_PLATFORMS; i++) {
            if (px + PLAYER_W > platforms[i].x && px < platforms[i].x + platforms[i].w &&
                py + PLAYER_H > platforms[i].y && py + PLAYER_H < platforms[i].y + platforms[i].h + 10 &&
                vy >= 0) {
                py = platforms[i].y - PLAYER_H;
                vy = 0;
                onGround = true;
            }
        }

        // Bounds
        if (px < 0) px = 0;
        if (px > W - PLAYER_W) px = W - PLAYER_W;
        if (py > H + 100) { py = H - 100; px = W / 2; vy = 0; } // respawn

        // Coin collection
        for (int i = 0; i < MAX_COINS; i++) {
            if (!coins[i].collected && fabs(px + PLAYER_W/2 - coins[i].x) < 20 && fabs(py + PLAYER_H/2 - coins[i].y) < 20) {
                coins[i].collected = true;
                score += 10;
            }
        }

        // Camera follow (simple)
        float camX = px - W / 2;
        if (camX < 0) camX = 0;

        BeginDrawing();
        ClearBackground((Color){ 135, 206, 235, 255 }); // sky blue

        // Draw platforms
        for (int i = 0; i < MAX_PLATFORMS; i++) {
            DrawRectangle(platforms[i].x - camX, platforms[i].y, platforms[i].w, platforms[i].h, platforms[i].color);
        }

        // Draw coins
        for (int i = 0; i < MAX_COINS; i++) {
            if (!coins[i].collected) {
                DrawCircle(coins[i].x - camX, coins[i].y, 8, GOLD);
                DrawCircle(coins[i].x - camX, coins[i].y, 5, YELLOW);
            }
        }

        // Draw player
        DrawRectangle(px - camX, py, PLAYER_W, PLAYER_H, BLUE);
        DrawRectangle(px - camX + 4, py + 4, 6, 6, WHITE);
        DrawRectangle(px - camX + 14, py + 4, 6, 6, WHITE);

        DrawText(TextFormat("Score: %d", score), 10, 10, 20, WHITE);
        DrawFPS(W - 80, 10);

        EndDrawing();
        frame++;
    }

    CloseWindow();
    return 0;
}
