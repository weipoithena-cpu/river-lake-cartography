/* RiverLakeCartography portable Windows launcher.
 * Starts the private Python runtime next to this executable, never a system Python.
 * Build: zig cc -target x86_64-windows-gnu -municode -Wl,--subsystem,windows -O2 launcher.c
 *        -o RiverLakeCartography.exe -luser32
 */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <wchar.h>
#include <stdio.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous,
                   PWSTR arguments, int show_command) {
    wchar_t directory[32768], executable[32768], script[32768], command[32768];
    DWORD length = GetModuleFileNameW(NULL, directory, 32768);
    if (!length || length >= 32767) return 2;
    wchar_t *last_slash = wcsrchr(directory, L'\\');
    if (!last_slash) return 2;
    *last_slash = L'\0';
    int has_arguments = arguments && *arguments;
    if (swprintf(executable, 32768, L"%ls\\runtime\\python.exe", directory) < 0 ||
        swprintf(script, 32768, L"%ls\\app\\main.py", directory) < 0) return 2;
    if (GetFileAttributesW(executable) == INVALID_FILE_ATTRIBUTES ||
        GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL,
            L"Application files are missing. Extract the complete ZIP before running RiverLakeCartography.exe.\nKeep the executable, app and runtime folders together.",
            L"River Lake Cartography", MB_OK | MB_ICONERROR);
        return 3;
    }
    if (swprintf(command, 32768, L"\"%ls\" \"%ls\" %ls", executable, script,
                 has_arguments ? arguments : L"") < 0) return 2;
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    ZeroMemory(&startup, sizeof(startup));
    ZeroMemory(&process, sizeof(process));
    startup.cb = sizeof(startup);
    HANDLE log_handle = INVALID_HANDLE_VALUE, input_handle = INVALID_HANDLE_VALUE;
    if (has_arguments) {
        startup.dwFlags = STARTF_USESTDHANDLES;
        startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
        startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
        startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    } else {
        /* A GUI launch has no console. Give Python real handles so startup
           diagnostics remain available even when Explorer supplied none. */
        wchar_t local_data[32768], log_directory[32768], log_path[32768];
        DWORD size = GetEnvironmentVariableW(L"LOCALAPPDATA", local_data, 32768);
        if (!size || size >= 32768) GetTempPathW(32768, local_data);
        swprintf(log_directory, 32768, L"%ls\\RiverLakeCartography", local_data);
        CreateDirectoryW(log_directory, NULL);
        swprintf(log_path, 32768, L"%ls\\startup.log", log_directory);
        SECURITY_ATTRIBUTES security = { sizeof(SECURITY_ATTRIBUTES), NULL, TRUE };
        log_handle = CreateFileW(log_path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                 &security, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        input_handle = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                   &security, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (log_handle != INVALID_HANDLE_VALUE && input_handle != INVALID_HANDLE_VALUE) {
            startup.dwFlags = STARTF_USESTDHANDLES;
            startup.hStdInput = input_handle;
            startup.hStdOutput = log_handle;
            startup.hStdError = log_handle;
        }
    }
    if (!CreateProcessW(executable, command, NULL, NULL, TRUE,
                        CREATE_NO_WINDOW, NULL, directory, &startup, &process)) {
        DWORD error = GetLastError();
        wchar_t detail[512];
        swprintf(detail, 512,
            L"Startup failed. Windows error code: %lu.\nUse 64-bit Windows 10/11 and extract the complete application first.",
            error);
        if (!has_arguments) MessageBoxW(NULL, detail, L"River Lake Cartography", MB_OK | MB_ICONERROR);
        if (log_handle != INVALID_HANDLE_VALUE) CloseHandle(log_handle);
        if (input_handle != INVALID_HANDLE_VALUE) CloseHandle(input_handle);
        return (int)error;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD exit_code = 1;
    GetExitCodeProcess(process.hProcess, &exit_code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    if (log_handle != INVALID_HANDLE_VALUE) CloseHandle(log_handle);
    if (input_handle != INVALID_HANDLE_VALUE) CloseHandle(input_handle);
    if (exit_code && !has_arguments) {
        MessageBoxW(NULL,
            L"The application stopped after an error. Run Check-Application.cmd to produce a diagnostic report, then share that report with technical support.",
            L"River Lake Cartography", MB_OK | MB_ICONERROR);
    }
    return (int)exit_code;
}
