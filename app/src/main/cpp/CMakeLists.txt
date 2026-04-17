cmake_minimum_required(VERSION 3.10.2)

# Оголошуємо нашу бібліотеку (назва native_stream)
add_library(native_stream SHARED native_stream.c)

# Знаходимо системні бібліотеки Android, які нам знадобляться
find_library(log-lib log)
find_library(android-lib android)

# Лінкуємо нашу бібліотеку з системними (для логів та малювання на екрані)
target_link_libraries(native_stream
                      ${log-lib}
                      ${android-lib})

target_link_libraries(native_stream log GLESv2)