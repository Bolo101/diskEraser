#ifndef MAIN_H
#define MAIN_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <process.h>

void select_disks();
void choose_filesystem();
void confirm_erasure(const char *disk);
void get_disk_confirmations(const char **disks, int *confirmed_count);
void process_disk(const char *disk, const char *fs_choice, int passes);
void sudo_check();
void app();

#endif /* MAIN_H */
