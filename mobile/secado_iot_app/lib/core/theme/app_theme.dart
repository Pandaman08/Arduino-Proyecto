import 'package:flutter/material.dart';

abstract final class AppTheme {
  static const forest = Color(0xFF173E32);
  static const cream = Color(0xFFF6F3EB);
  static const coffee = Color(0xFF795548);
  static ThemeData get light => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: forest,
          primary: forest,
          secondary: coffee,
          surface: const Color(0xFFFFFDF8),
        ),
        scaffoldBackgroundColor: cream,
        appBarTheme: const AppBarTheme(
          backgroundColor: cream,
          foregroundColor: forest,
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
        ),
        navigationBarTheme: const NavigationBarThemeData(
          backgroundColor: Color(0xFFFFFDF8),
        ),
      );
}
