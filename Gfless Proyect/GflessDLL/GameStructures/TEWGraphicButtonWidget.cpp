#include "TEWGraphicButtonWidget.h"

void TEWGraphicButtonWidget::setSelectedIndex(const int32_t i)
{
	selectedIndex = i;
}

void TEWGraphicButtonWidget::click()
{
        uint32_t parametersAddress = parameters;
        uint32_t callAddress = clickFunction;
        TEWGraphicButtonWidget* selfButton = this;

#ifdef _MSC_VER
        __asm {
                mov eax, parametersAddress
                mov edx, selfButton
                call callAddress
        }
#else
        __asm__ __volatile__(
                "mov eax, %[param]\n"
                "mov edx, %[self]\n"
                "call %[call]\n"
                :
                : [param] "r"(parametersAddress),
                  [self] "r"(selfButton),
                  [call] "r"(callAddress)
                : "eax", "edx");
#endif
}