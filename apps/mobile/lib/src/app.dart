import 'dart:async';

import 'package:flutter/material.dart';

import 'connectors/docker_connector.dart';
import 'connectors/grafana_connector.dart';
import 'connectors/home_assistant_connector.dart';
import 'connectors/knowledge_connector.dart';
import 'connectors/prometheus_connector.dart';
import 'connectors/storage_connector.dart';
import 'connectors/synology_connector.dart';
import 'connectors/unifi_connector.dart';
import 'connectors/ups_connector.dart';
import 'core/project_context_provider.dart';
import 'core/siris_context_service.dart';
import 'core/siris_integration_manager.dart';
import 'screens/app_shell.dart';
import 'screens/grafana_screen.dart';
import 'screens/home_assistant_screen.dart';
import 'screens/login_screen.dart';
import 'screens/mission_control_screen.dart';
import 'screens/operations_center_screen.dart';
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
    if (authenticated) {
      unawaited(_startIntegrations());
    }
  }

  Future<void> _startIntegrations() async {
    for (final connector in [
      DockerConnector(),
      HomeAssistantConnector(),
      PrometheusConnector(),
      GrafanaConnector(),
      UniFiConnector(),
      StorageConnector(),
      SynologyConnector(),
      UpsConnector(),
      KnowledgeConnector(),
    ]) {
      try {
        await SirisIntegrationManager.instance.register(connector);
      } catch (_) {
        // Integration health is tracked by SirisIntegrationManager. A slow or
        // unavailable external integration must never block the core app shell.
      }
    }
    SirisCoreContextService.instance.register(ProjectContextProvider());
    await SirisCoreContextService.instance.initializeDefaults();
  }

  Future<void> _onAuthenticated() async {
    if (mounted) setState(() => _authenticated = true);
    unawaited(_startIntegrations());
  }

  Future<void> _logout() async {
    await SirisCoreContextService.instance.dispose();
    await SirisIntegrationManager.instance.dispose();
    await _authService.logout();
    if (mounted) setState(() => _authenticated = false);
  }

  Widget _authenticatedRoute(Widget child) =>
      _authenticated ? child : LoginScreen(onAuthenticated: _onAuthenticated);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SirisOS',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      routes: {
        MissionControlScreen.routeName: (_) =>
            _authenticatedRoute(const MissionControlScreen()),
        OperationsCenterScreen.routeName: (_) =>
            _authenticatedRoute(const OperationsCenterScreen()),
        HomeAssistantScreen.routeName: (_) =>
            _authenticatedRoute(const HomeAssistantScreen()),
        GrafanaScreen.routeName: (_) => _authenticatedRoute(const GrafanaScreen()),
      },
      home: _checkingSession
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : _authenticated
              ? AppShell(onLogout: _logout)
              : LoginScreen(onAuthenticated: _onAuthenticated),
    );
  }
}
