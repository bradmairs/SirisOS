import 'package:flutter/material.dart';

abstract final class AppTheme {
  static const background = Color(0xFF050C16);
  static const sidebar = Color(0xFF07111F);
  static const surface = Color(0xFF0B1726);
  static const surfaceRaised = Color(0xFF0F2033);
  static const border = Color(0xFF1A3550);
  static const primary = Color(0xFF3B82F6);
  static const cyan = Color(0xFF38BDF8);
  static const success = Color(0xFF63D83A);

  static ThemeData get dark {
    const scheme = ColorScheme.dark(
      primary: primary,
      secondary: cyan,
      surface: surface,
      error: Color(0xFFFF7A45),
      onPrimary: Colors.white,
      onSurface: Color(0xFFF5F8FC),
      onSurfaceVariant: Color(0xFF93A4B8),
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
          borderRadius: BorderRadius.all(Radius.circular(18)),
        ),
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(fontWeight: FontWeight.w800, letterSpacing: -0.8),
        headlineSmall: TextStyle(fontWeight: FontWeight.w800, letterSpacing: -0.5),
        titleLarge: TextStyle(fontWeight: FontWeight.w750),
        titleMedium: TextStyle(fontWeight: FontWeight.w650),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: sidebar,
        indicatorColor: primary.withValues(alpha: 0.18),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            color: states.contains(WidgetState.selected) ? Colors.white : scheme.onSurfaceVariant,
            fontWeight: states.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
      navigationRailTheme: const NavigationRailThemeData(
        backgroundColor: sidebar,
        indicatorColor: Color(0x263B82F6),
        selectedIconTheme: IconThemeData(color: cyan),
        unselectedIconTheme: IconThemeData(color: Color(0xFF8FA1B7)),
        selectedLabelTextStyle: TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
        unselectedLabelTextStyle: TextStyle(color: Color(0xFFB5C0CE)),
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
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: primary,
        foregroundColor: Colors.white,
      ),
    );
  }
}
