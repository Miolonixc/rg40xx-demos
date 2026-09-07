#include "raylib.h"
#include <math.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define GRID_W 32
#define GRID_H 24
#define CELL 20
#define MAX_BALLS 8

typedef struct {
    float x, y, vx, vy, r;
    Color color;
    int paddleId;
} Ball;

typedef struct {
    float x, y, w, h, speed, targetY;
    int score;
    Color color;
} Paddle;

int main(void) {
    InitWindow(W, H, "Pong Multi");
    SetTargetFPS(60);
    bool hasPad = IsGamepadAvailable(0);
    srand(time(NULL));

    Paddle paddles[2];
    paddles[0] = (Paddle){ 20, H/2 - 40, 15, 80, 5, H/2, 0, RED };
    paddles[1] = (Paddle){ W - 35, H/2 - 40, 15, 80, 5, H/2, 0, BLUE };

    Ball balls[MAX_BALLS];
    int ballCount = 1;
    balls[0] = (Ball){ W/2, H/2, 4, 3, 8, WHITE, -1 };

    bool paused = false;

    while (!WindowShouldClose()) {
        if (IsKeyPressed(KEY_P) || (hasPad && IsGamepadButtonPressed(0, 6))) paused = !paused;
        
        if (!paused) {
            // Paddle 1 (W/S)
            if (IsKeyDown(KEY_W) || (hasPad && GetGamepadAxisMovement(0,1) < -0.3f)) paddles[0].y -= paddles[0].speed;
            if (IsKeyDown(KEY_S) || (hasPad && GetGamepadAxisMovement(0,1) > 0.3f)) paddles[0].y += paddles[0].speed;

            // Paddle 2 (Up/Down)
            if (IsKeyDown(KEY_UP)) paddles[1].y -= paddles[1].speed;
            if (IsKeyDown(KEY_DOWN)) paddles[1].y += paddles[1].speed;

            // Clamp paddles
            for (int i = 0; i < 2; i++) {
                if (paddles[i].y < 0) paddles[i].y = 0;
                if (paddles[i].y > H - paddles[i].h) paddles[i].y = H - paddles[i].h;
            }

            // Update balls
            for (int b = 0; b < ballCount; b++) {
                balls[b].x += balls[b].vx;
                balls[b].y += balls[b].vy;

                // Wall bounce top/bottom
                if (balls[b].y < balls[b].r || balls[b].y > H - balls[b].r) balls[b].vy *= -1;

                // Paddle collision
                for (int i = 0; i < 2; i++) {
                    if (balls[b].x - balls[b].r < paddles[i].x + paddles[i].w &&
                        balls[b].x + balls[b].r > paddles[i].x &&
                        balls[b].y > paddles[i].y && balls[b].y < paddles[i].y + paddles[i].h) {
                        balls[b].vx *= -1.05f;
                        balls[b].x = (i == 0) ? paddles[i].x + paddles[i].w + balls[b].r : paddles[i].x - balls[b].r;
                        // Add spin based on hit position
                        float hitPos = (balls[b].y - paddles[i].y) / paddles[i].h - 0.5f;
                        balls[b].vy += hitPos * 3;
                    }
                }

                // Score
                if (balls[b].x < 0) { paddles[1].score++; balls[b].x = W/2; balls[b].y = H/2; balls[b].vx = -4; }
                if (balls[b].x > W) { paddles[0].score++; balls[b].x = W/2; balls[b].y = H/2; balls[b].vx = 4; }

                // Speed limit
                if (fabs(balls[b].vx) > 10) balls[b].vx = (balls[b].vx > 0) ? 10 : -10;
            }

            // Add ball every 5 points
            int totalScore = paddles[0].score + paddles[1].score;
            if (totalScore > 0 && totalScore % 5 == 0 && ballCount < MAX_BALLS) {
                balls[ballCount] = (Ball){ W/2, H/2, (rand()%2==0)?4:-4, rand()%3-1, 8, YELLOW, -1 };
                ballCount++;
            }
        }

        BeginDrawing();
        ClearBackground(BLACK);
        
        // Center line
        for (int i = 0; i < H; i += 20) DrawRectangle(W/2 - 2, i, 4, 10, DARKGRAY);

        // Paddles
        for (int i = 0; i < 2; i++) {
            DrawRectangle(paddles[i].x, paddles[i].y, paddles[i].w, paddles[i].h, paddles[i].color);
        }

        // Balls
        for (int b = 0; b < ballCount; b++) {
            DrawCircle(balls[b].x, balls[b].y, balls[b].r, balls[b].color);
        }

        // Scores
        DrawText(TextFormat("%d", paddles[0].score), W/4, 20, 40, RED);
        DrawText(TextFormat("%d", paddles[1].score), 3*W/4, 20, 40, BLUE);

        if (paused) DrawText("PAUSED", W/2 - 60, H/2, 40, YELLOW);
        DrawFPS(W - 80, 10);
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
