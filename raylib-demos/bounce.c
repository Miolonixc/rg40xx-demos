#include "raylib.h"
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define BLOCKS 12

typedef struct {
    float x, y, w, h, vx;
    Color color;
} Block;

int main(void) {
    InitWindow(W, H, "Raylib Bounce");
    SetTargetFPS(60);
    
    // Try to use gamepad if available
    bool hasPad = IsGamepadAvailable(0);

    Block blocks[BLOCKS];
    srand(time(NULL));
    for (int i = 0; i < BLOCKS; i++) {
        blocks[i].x = rand() % (W - 60);
        blocks[i].y = rand() % (H - 200) + 50;
        blocks[i].w = rand() % 40 + 30;
        blocks[i].h = rand() % 20 + 15;
        blocks[i].vx = (rand() % 100 - 50) / 25.0f;
        blocks[i].color = (Color){ rand() % 200 + 55, rand() % 200 + 55, rand() % 200 + 55, 255 };
    }

    float ballX = W / 2, ballY = H / 2, ballVx = 3, ballVy = 3;
    float ballR = 12;

    while (!WindowShouldClose()) {
        // Input
        if (hasPad) {
            ballVx += GetGamepadAxisMovement(0, 0) * 0.5f;
            ballVy += GetGamepadAxisMovement(0, 1) * 0.5f;
        }
        if (IsKeyDown(KEY_LEFT) || IsKeyDown(KEY_A)) ballVx -= 0.3f;
        if (IsKeyDown(KEY_RIGHT) || IsKeyDown(KEY_D)) ballVx += 0.3f;
        if (IsKeyDown(KEY_UP) || IsKeyDown(KEY_W)) ballVy -= 0.3f;
        if (IsKeyDown(KEY_DOWN) || IsKeyDown(KEY_S)) ballVy += 0.3f;

        // Update blocks
        for (int i = 0; i < BLOCKS; i++) {
            blocks[i].x += blocks[i].vx;
            if (blocks[i].x < 0 || blocks[i].x + blocks[i].w > W) blocks[i].vx *= -1;
        }

        // Update ball
        ballX += ballVx;
        ballY += ballVy;
        if (ballX < ballR || ballX > W - ballR) { ballVx *= -0.9f; ballX = (ballX < ballR) ? ballR : W - ballR; }
        if (ballY < ballR || ballY > H - ballR) { ballVy *= -0.9f; ballY = (ballY < ballR) ? ballR : H - ballR; }
        
        // Friction
        ballVx *= 0.995f;
        ballVy *= 0.995f;

        // Draw
        BeginDrawing();
        ClearBackground((Color){ 15, 15, 25, 255 });
        
        for (int i = 0; i < BLOCKS; i++) {
            DrawRectangle((int)blocks[i].x, (int)blocks[i].y, (int)blocks[i].w, (int)blocks[i].h, blocks[i].color);
        }
        
        DrawCircle((int)ballX, (int)ballY, ballR, WHITE);
        DrawCircleGradient((Vector2){ballX, ballY}, ballR, YELLOW, RED);
        
        DrawText("Arrows/WASD + Gamepad", 10, 10, 20, LIGHTGRAY);
        DrawFPS(W - 80, 10);
        
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
