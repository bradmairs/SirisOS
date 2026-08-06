import 'package:flutter/material.dart';

import 'screens/app_shell.dart';
import 'screens/login_screen.dart';
import 'screens/mission_control_screen.dart';
import 'services/auth_service.dart';
import 'theme/app_theme.dart';

class SirisOsApp extends StatefulWidget {
  const SirisOsApp({super.key});

  @override
  State<SirisOsApp> createState() => _SirisOsAppState();
}

class _SirisOsAppState extends State<SirisOsApp> {
  final AuthService _authService = AuthService();
  bool _checkingSession = true;
  bool _authenticated = false;

  @override
  void initState() {
    super.initState();
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    final authenticated = await _authService.restoreSession();
    if (!mounted) return;
    setState(() {
      _authenticated = authenticated;
      _checkingSession = false;
    });
  }

  Future<void> _logout() async {
    await _authService.logout();
    if (mounted) setState(() => _authenticated = false);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SirisOS',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      routes: {
        MissionControlScreen.routeName: (_) => _authenticated
            ? const MissionControlScreen()
            : LoginScreen(
                onAuthenticated: () => setState(() => _authenticated = true),
              ),
      },
      home: _checkingSession
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : _authenticated
              ? AppShell(onLogout: _logout)
              : LoginScreen(
                  onAuthenticated: () => setState(() => _authenticated = true),
                ),
    );
  }
}
