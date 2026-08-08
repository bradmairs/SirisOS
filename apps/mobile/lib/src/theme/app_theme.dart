import 'package:flutter/material.dart';

abstract final class AppTheme {
  static const background = Color(0xFF070708);
  static const sidebar = Color(0xFF0B0B0D);
  static const surface = Color(0xFF111114);
  static const surfaceRaised = Color(0xFF18181C);
  static const border = Color(0xFF2A2528);
  static const primary = Color(0xFFE5484D);
  static const primaryBright = Color(0xFFFF5A5F);
  static const info = Color(0xFF61A8FF);
  static const success = Color(0xFF61D69A);
  static const warning = Color(0xFFF6B85C);

  static ThemeData get dark {
    const scheme = ColorScheme.dark(
      primary: primary,
      secondary: primaryBright,
      secondaryContainer: Color(0xFF5B2428),
      onSecondaryContainer: Colors.white,
      surface: surface,
      error: Color(0xFFFF5D5D),
      onPrimary: Colors.white,
      onSurface: Color(0xFFF7F5F5),
      onSurfaceVariant: Color(0xFFA7A0A3),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: background,
      dividerColor: border,
      cardTheme: const CardThemeData(
        color: surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          side: BorderSide(color: border),
          borderRadius: BorderRadius.all(Radius.circular(20)),
        ),
      ),
      textTheme: const TextTheme(
        displayLarge: TextStyle(
          fontWeight: FontWeight.w300,
          letterSpacing: -2.4,
        ),
        headlineMedium: TextStyle(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.9,
        ),
        headlineSmall: TextStyle(
          fontWeight: FontWeight.w800,
          letterSpacing: -0.6,
        ),
        titleLarge: TextStyle(fontWeight: FontWeight.w700),
        titleMedium: TextStyle(fontWeight: FontWeight.w600),
        labelSmall: TextStyle(fontWeight: FontWeight.w700),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: surfaceRaised,
        selectedColor: primary.withValues(alpha: 0.2),
        side: const BorderSide(color: border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        labelStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: sidebar,
        indicatorColor: primary.withValues(alpha: 0.18),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            color: states.contains(WidgetState.selected)
                ? Colors.white
                : scheme.onSurfaceVariant,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w700
                : FontWeight.w500,
          ),
        ),
      ),
      navigationRailTheme: const NavigationRailThemeData(
        backgroundColor: sidebar,
        indicatorColor: Color(0x33E5484D),
        selectedIconTheme: IconThemeData(color: primaryBright),
        unselectedIconTheme: IconThemeData(color: Color(0xFFA39A9E)),
        selectedLabelTextStyle: TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w700,
        ),
        unselectedLabelTextStyle: TextStyle(color: Color(0xFFB9B2B5)),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        filled: true,
        fillColor: surfaceRaised,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(14)),
          borderSide: BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(14)),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(14)),
          borderSide: BorderSide(color: primary),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: primary,
        foregroundColor: Colors.white,
      ),
    );
  }
}
