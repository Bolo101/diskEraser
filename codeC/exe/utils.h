#ifndef UTILS_H
#define UTILS_H

#include <stdio.h>

void list_disks();
int run_command(const char *command);

// Function to display a progress bar
void display_progress(const char *message, int duration);

#endif // UTILS_H
