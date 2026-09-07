#include "raylib.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define W 640
#define H 480
#define PLAYER_SPEED 4
#define BULLET_SPEED 8
#define MAX_BULLETS 32
#define MAX_ENEMIES 16
#define MAX_STARS 100

typedef struct { float x, y; } Vec2;
typedef struct { float x, y, vy; bool active; } Bullet;
typedef struct { float x, y, vy, hp; bool active; } Enemy;

int main(void) {
    InitWindow(W, H, "Space Shooter");
    SetTargetFPS(60);
    bool hasPad = IsGamepadAvailable(0);

    // Stars background
    Vec2 stars[MAX_STARS];
    srand(time(NULL));
    for (int i = 0; i < MAX_STARS; i++) {
        stars[i].x = rand() % W;
        stars[i].y = rand() % H;
    }

    float playerX = W / 2, playerY = H - 60;
    Bullet bullets[MAX_BULLETS] = {0};
    Enemy enemies[MAX_ENEMIES] = {0};
    int score = 0, lives = 3, frame = 0;
    bool gameOver = false;

    while (!WindowShouldClose()) {
        if (!gameOver) {
            // Input
            float ax = hasPad ? GetGamepadAxisMovement(0, 0) : 0;
            if (IsKeyDown(KEY_LEFT) || IsKeyDown(KEY_A) || ax < -0.3f) playerX -= PLAYER_SPEED;
            if (IsKeyDown(KEY_RIGHT) || IsKeyDown(KEY_D) || ax > 0.3f) playerX += PLAYER_SPEED;
            playerX = fmax(15, fmin(W - 15, playerX));

            // Shoot
            if ((IsKeyPressed(KEY_SPACE) || IsKeyPressed(KEY_Z) || IsKeyPressed(KEY_J) || 
                 (hasPad && IsGamepadButtonPressed(0, 0))) && frame % 8 == 0) {
                for (int i = 0; i < MAX_BULLETS; i++) {
                    if (!bullets[i].active) {
                        bullets[i] = (Bullet){ playerX, playerY - 10, -BULLET_SPEED, true };
                        break;
                    }
                }
            }

            // Spawn enemies
            if (frame % 30 == 0) {
                for (int i = 0; i < MAX_ENEMIES; i++) {
                    if (!enemies[i].active) {
                        enemies[i] = (Enemy){ rand() % (W - 30) + 15, -20, 1.0f + rand() % 3, 1, true };
                        break;
                    }
                }
            }

            // Update bullets
            for (int i = 0; i < MAX_BULLETS; i++) {
                if (bullets[i].active) {
                    bullets[i].y += bullets[i].vy;
                    if (bullets[i].y < 0) bullets[i].active = false;
                }
            }

            // Update enemies
            for (int i = 0; i < MAX_ENEMIES; i++) {
                if (enemies[i].active) {
                    enemies[i].y += enemies[i].vy;
                    if (enemies[i].y > H) { enemies[i].active = false; lives--; if (lives <= 0) gameOver = true; }
                }
            }

            // Collision
            for (int i = 0; i < MAX_BULLETS; i++) {
                if (!bullets[i].active) continue;
                for (int j = 0; j < MAX_ENEMIES; j++) {
                    if (!enemies[j].active) continue;
                    if (fabs(bullets[i].x - enemies[j].x) < 20 && fabs(bullets[i].y - enemies[j].y) < 20) {
                        bullets[i].active = false;
                        enemies[j].active = false;
                        score += 100;
                    }
                }
            }

            frame++;
        } else {
            if (IsKeyPressed(KEY_R) || (hasPad && IsGamepadButtonPressed(0, 7))) {
                gameOver = false; score = 0; lives = 3; frame = 0;
                memset(bullets, 0, sizeof(bullets));
                memset(enemies, 0, sizeof(enemies));
            }
        }

        // Update stars
        for (int i = 0; i < MAX_STARS; i++) {
            stars[i].y += 0.5f;
            if (stars[i].y > H) { stars[i].y = 0; stars[i].x = rand() % W; }
        }

        BeginDrawing();
        ClearBackground(BLACK);

        // Stars
        for (int i = 0; i < MAX_STARS; i++) DrawPixel((int)stars[i].x, (int)stars[i].y, WHITE);

        // Player (triangle)
        DrawTriangle((Vector2){playerX, playerY - 12}, (Vector2){playerX - 12, playerY + 10}, (Vector2){playerX + 12, playerY + 10}, GREEN);

        // Bullets
        for (int i = 0; i < MAX_BULLETS; i++) {
            if (bullets[i].active) DrawRectangle((int)bullets[i].x - 2, (int)bullets[i].y, 4, 10, YELLOW);
        }

        // Enemies
        for (int i = 0; i < MAX_ENEMIES; i++) {
            if (enemies[i].active) DrawCircle((int)enemies[i].x, (int)enemies[i].y, 12, RED);
        }

        DrawText(TextFormat("Score: %d", score), 10, 10, 20, WHITE);
        DrawText(TextFormat("Lives: %d", lives), 10, 35, 20, WHITE);

        if (gameOver) DrawText("GAME OVER - R/Start", W / 2 - 160, H / 2, 30, YELLOW);
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
