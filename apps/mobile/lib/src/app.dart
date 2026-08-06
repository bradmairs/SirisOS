import 'package:flutter/material.dart';

import 'screens/app_shell.dart';
import 'theme/app_theme.dart';

class SirisOsApp extends StatelessWidget {
  const SirisOsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SirisOS',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      home: const AppShell(),
    );
  }
}
