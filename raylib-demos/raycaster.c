#include "raylib.h"
#include <math.h>
#include <stdlib.h>
#include <time.h>

#define W 640
#define H 480
#define MAP_SIZE 16
#define CELL_SIZE 40
#define FOV 60

// Simple maze map (1 = wall, 0 = empty)
int map[MAP_SIZE][MAP_SIZE] = {
    {1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1},
    {1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1},
    {1,0,1,1,0,1,1,1,0,1,1,1,0,1,0,1},
    {1,0,1,0,0,0,0,1,0,0,0,1,0,1,0,1},
    {1,0,1,0,1,1,0,1,1,1,0,1,0,1,0,1},
    {1,0,0,0,1,0,0,0,0,0,0,0,0,0,0,1},
    {1,1,1,0,1,0,1,1,1,1,1,1,0,1,1,1},
    {1,0,0,0,0,0,1,0,0,0,0,1,0,0,0,1},
    {1,0,1,1,1,0,1,0,1,1,0,1,0,1,0,1},
    {1,0,1,0,0,0,0,0,1,0,0,0,0,1,0,1},
    {1,0,1,0,1,1,1,0,1,0,1,1,1,1,0,1},
    {1,0,0,0,1,0,0,0,0,0,0,0,0,0,0,1},
    {1,1,1,0,1,0,1,1,1,1,1,1,0,1,1,1},
    {1,0,0,0,0,0,1,0,0,0,0,1,0,0,0,1},
    {1,0,1,1,1,0,0,0,1,1,0,0,0,1,0,1},
    {1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1}
};

typedef struct {
    float x, y, angle;
} Player;

int main(void) {
    InitWindow(W, H, "Raycaster");
    SetTargetFPS(60);
    bool hasPad = IsGamepadAvailable(0);

    Player player = { 2.5f * CELL_SIZE, 2.5f * CELL_SIZE, 0 };

    while (!WindowShouldClose()) {
        // Input
        float ax = hasPad ? GetGamepadAxisMovement(0, 0) : 0;
        float ay = hasPad ? GetGamepadAxisMovement(0, 1) : 0;

        if (IsKeyDown(KEY_LEFT) || IsKeyDown(KEY_A) || ax < -0.3f) player.angle -= 2.5f;
        if (IsKeyDown(KEY_RIGHT) || IsKeyDown(KEY_D) || ax > 0.3f) player.angle += 2.5f;

        float speed = 2.0f;
        if (IsKeyDown(KEY_UP) || IsKeyDown(KEY_W) || ay < -0.3f) {
            player.x += cos(player.angle * DEG2RAD) * speed;
            player.y += sin(player.angle * DEG2RAD) * speed;
        }
        if (IsKeyDown(KEY_DOWN) || IsKeyDown(KEY_S) || ay > 0.3f) {
            player.x -= cos(player.angle * DEG2RAD) * speed;
            player.y -= sin(player.angle * DEG2RAD) * speed;
        }

        // Wall collision
        int mx = (int)(player.x / CELL_SIZE);
        int my = (int)(player.y / CELL_SIZE);
        if (map[my][mx] == 1) {
            player.x -= cos(player.angle * DEG2RAD) * speed;
            player.y -= sin(player.angle * DEG2RAD) * speed;
        }

        BeginDrawing();
        ClearBackground(BLACK);

        // Draw ceiling and floor
        DrawRectangle(0, 0, W, H/2, (Color){ 50, 50, 70, 255 });
        DrawRectangle(0, H/2, W, H/2, (Color){ 30, 30, 30, 255 });

        // Raycasting
        for (int x = 0; x < W; x++) {
            float rayAngle = player.angle - FOV/2 + (x * FOV / W);
            float rayX = cos(rayAngle * DEG2RAD);
            float rayY = sin(rayAngle * DEG2RAD);

            float dist = 0;
            bool hit = false;
            while (!hit && dist < 20 * CELL_SIZE) {
                dist += 1;
                int testX = (int)(player.x + rayX * dist) / CELL_SIZE;
                int testY = (int)(player.y + rayY * dist) / CELL_SIZE;
                if (testX < 0 || testX >= MAP_SIZE || testY < 0 || testY >= MAP_SIZE) {
                    hit = true;
                    dist = 20 * CELL_SIZE;
                } else if (map[testY][testX] == 1) {
                    hit = true;
                }
            }

            // Fix fisheye
            dist = dist * cos((rayAngle - player.angle) * DEG2RAD);
            int lineHeight = (int)(H * CELL_SIZE / dist);
            int drawStart = H/2 - lineHeight/2;
            int drawEnd = H/2 + lineHeight/2;

            // Color based on distance
            int c = (int)(255 * (1.0f - dist / (20 * CELL_SIZE)));
            if (c < 30) c = 30;
            Color wallColor = { c, c/2, c/2, 255 };

            DrawLine(x, drawStart, x, drawEnd, wallColor);
        }

        // Minimap
        DrawRectangle(5, 5, MAP_SIZE * 4, MAP_SIZE * 4, (Color){ 0, 0, 0, 150 });
        for (int y = 0; y < MAP_SIZE; y++) {
            for (int x = 0; x < MAP_SIZE; x++) {
                if (map[y][x] == 1) DrawRectangle(5 + x*4, 5 + y*4, 4, 4, WHITE);
            }
        }
        DrawCircle(5 + (player.x/CELL_SIZE)*4, 5 + (player.y/CELL_SIZE)*4, 2, RED);

        DrawFPS(W - 80, 10);
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
