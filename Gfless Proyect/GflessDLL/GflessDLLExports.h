#ifndef GFLESS_DLL_EXPORTS_H
#define GFLESS_DLL_EXPORTS_H

#ifdef __cplusplus
extern "C" {
#endif

__declspec(dllexport) void Gfless_SelectLanguage(int lang);
__declspec(dllexport) void Gfless_SelectServer(int server);
__declspec(dllexport) void Gfless_SelectChannel(int channel);
__declspec(dllexport) void Gfless_SelectCharacter(int character);
__declspec(dllexport) void Gfless_ClickStart();

#ifdef __cplusplus
}
#endif

#endif // GFLESS_DLL_EXPORTS_H