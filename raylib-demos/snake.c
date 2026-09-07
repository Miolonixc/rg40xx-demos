#include "raylib.h"
#include <math.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define SNAKE_MAX 256

typedef struct {
    int x, y;
} Point;

int main(void) {
    InitWindow(W, H, "Snake");
    SetTargetFPS(10);
    bool hasPad = IsGamepadAvailable(0);

    Point snake[SNAKE_MAX];
    int snakeLen = 4;
    int dirX = 1, dirY = 0;
    int nextDirX = 1, nextDirY = 0;
    int cellSize = 20;
    int gridW = W / cellSize;
    int gridH = H / cellSize;

    for (int i = 0; i < snakeLen; i++) {
        snake[i].x = gridW / 2 - i;
        snake[i].y = gridH / 2;
    }

    Point food;
    bool gameOver = false;
    int score = 0;

    srand(time(NULL));
    food.x = rand() % gridW;
    food.y = rand() % gridH;

    while (!WindowShouldClose()) {
        // Input
        if (hasPad) {
            if (GetGamepadAxisMovement(0, 0) < -0.5f && dirX != 1) { nextDirX = -1; nextDirY = 0; }
            if (GetGamepadAxisMovement(0, 0) > 0.5f && dirX != -1) { nextDirX = 1; nextDirY = 0; }
            if (GetGamepadAxisMovement(0, 1) < -0.5f && dirY != 1) { nextDirX = 0; nextDirY = -1; }
            if (GetGamepadAxisMovement(0, 1) > 0.5f && dirY != -1) { nextDirX = 0; nextDirY = 1; }
        }
        if ((IsKeyDown(KEY_LEFT) || IsKeyDown(KEY_A)) && dirX != 1) { nextDirX = -1; nextDirY = 0; }
        if ((IsKeyDown(KEY_RIGHT) || IsKeyDown(KEY_D)) && dirX != -1) { nextDirX = 1; nextDirY = 0; }
        if ((IsKeyDown(KEY_UP) || IsKeyDown(KEY_W)) && dirY != 1) { nextDirX = 0; nextDirY = -1; }
        if ((IsKeyDown(KEY_DOWN) || IsKeyDown(KEY_S)) && dirY != -1) { nextDirX = 0; nextDirY = 1; }

        if (!gameOver) {
            dirX = nextDirX;
            dirY = nextDirY;

            // Move
            for (int i = snakeLen - 1; i > 0; i--) {
                snake[i] = snake[i - 1];
            }
            snake[0].x += dirX;
            snake[0].y += dirY;

            // Wall collision
            if (snake[0].x < 0 || snake[0].x >= gridW || snake[0].y < 0 || snake[0].y >= gridH) {
                gameOver = true;
            }

            // Self collision
            for (int i = 1; i < snakeLen; i++) {
                if (snake[0].x == snake[i].x && snake[0].y == snake[i].y) {
                    gameOver = true;
                    break;
                }
            }

            // Eat food
            if (snake[0].x == food.x && snake[0].y == food.y) {
                snakeLen++;
                score += 10;
                food.x = rand() % gridW;
                food.y = rand() % gridH;
            }
        } else {
            if (IsKeyPressed(KEY_R) || (hasPad && IsGamepadButtonPressed(0, 7))) {
                gameOver = false;
                snakeLen = 4;
                dirX = 1; dirY = 0;
                nextDirX = 1; nextDirY = 0;
                for (int i = 0; i < snakeLen; i++) {
                    snake[i].x = gridW / 2 - i;
                    snake[i].y = gridH / 2;
                }
                score = 0;
            }
        }

        BeginDrawing();
        ClearBackground(BLACK);

        // Draw food
        DrawRectangle(food.x * cellSize + 2, food.y * cellSize + 2, cellSize - 4, cellSize - 4, RED);

        // Draw snake
        for (int i = 0; i < snakeLen; i++) {
            Color c = i == 0 ? GREEN : DARKGREEN;
            DrawRectangle(snake[i].x * cellSize + 1, snake[i].y * cellSize + 1, cellSize - 2, cellSize - 2, c);
        }

        DrawText(TextFormat("Score: %d", score), 10, 10, 20, WHITE);
        
        if (gameOver) {
            DrawText("GAME OVER - Press R/Start", W / 2 - 180, H / 2, 30, YELLOW);
        }

        EndDrawing();
    }

    CloseWindow();
    return 0;
}
