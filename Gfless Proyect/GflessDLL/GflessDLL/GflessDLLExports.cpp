#include "GflessDLLExports.h"
#include "GameStructures/TNTNewServerSelectWidget2.h"
#include "GameStructures/TCharacterSelectWidget.h"

static TNTNewServerSelectWidget2* GetServerWidget()
{
    return TNTNewServerSelectWidget2::getInstance();
}

static TCharacterSelectWidget* GetCharacterWidget()
{
    return TCharacterSelectWidget::getInstance();
}

void Gfless_SelectLanguage(int lang)
{
    if (auto widget = GetServerWidget())
    {
        widget->selectLanguage(lang);
    }
}

void Gfless_SelectServer(int server)
{
    if (auto widget = GetServerWidget())
    {
        widget->selectServer(server);
    }
}

void Gfless_SelectChannel(int channel)
{
    if (auto widget = GetServerWidget())
    {
        widget->selectChannel(channel);
    }
}

void Gfless_SelectCharacter(int character)
{
    if (auto widget = GetCharacterWidget())
    {
        widget->clickCharacterButton(character);
    }
}

void Gfless_ClickStart()
{
    if (auto widget = GetCharacterWidget())
    {
        widget->clickStartButton();
    }
}