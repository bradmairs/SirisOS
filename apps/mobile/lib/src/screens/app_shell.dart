import 'package:flutter/material.dart';

import '../core/module_registry.dart';
import '../models/dashboard_summary.dart';
import '../services/dashboard_service.dart';
import '../theme/app_theme.dart';
import '../widgets/siris_logo.dart';
import 'dashboard_screen.dart';
import 'global_search_screen.dart';
import 'gym_screen.dart';
import 'health_screen.dart';
import 'homelab_screen.dart';
import 'notification_center_screen.dart';
import 'running_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({required this.onLogout, super.key});

  final Future<void> Function() onLogout;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  final DashboardService _dashboardService = DashboardService();
  final List<SirisModuleDefinition> _navigationModules =
      SirisModuleRegistry.navigationModules;

  int _selectedIndex = 0;
  int _runAddRequest = 0;
  int _workoutAddRequest = 0;
  late Future<DashboardSummary> _sidebarFuture;

  @override
  void initState() {
    super.initState();
    _sidebarFuture = _dashboardService.fetchDashboard();
  }

  void _selectTab(int index) => setState(() => _selectedIndex = index);

  void _selectModule(String moduleId) {
    final index = SirisModuleRegistry.navigationIndexOf(moduleId);
    if (index >= 0) _selectTab(index);
  }

  void _openRunForm() => setState(() {
        _selectedIndex = SirisModuleRegistry.navigationIndexOf('running');
        _runAddRequest++;
      });

  void _openWorkoutForm() => setState(() {
        _selectedIndex = SirisModuleRegistry.navigationIndexOf('gym');
        _workoutAddRequest++;
      });

  void _openSearchTarget(String target) {
    if (target == 'notifications') {
      Navigator.of(context).push<void>(
        MaterialPageRoute<void>(
          builder: (_) => const NotificationCenterScreen(),
        ),
      );
      return;
    }
    _selectModule(target);
  }

  Future<void> _openSearch() => Navigator.of(context).push<void>(
        MaterialPageRoute<void>(
          builder: (_) => GlobalSearchScreen(onOpenTarget: _openSearchTarget),
        ),
      );

  Widget _screenFor(SirisModuleDefinition module) => switch (module.id) {
        'dashboard' => const DashboardScreen(),
        'homelab' => const HomelabScreen(),
        'running' => RunningScreen(addRequest: _runAddRequest),
        'gym' => GymScreen(addRequest: _workoutAddRequest),
        'health' => const HealthScreen(),
        'siris' => const _ComingSoonScreen(),
        _ => _UnknownModuleScreen(module: module),
      };

  void _performModuleAction(SirisModuleDefinition module) {
    switch (module.primaryAction) {
      case SirisModuleAction.logRun:
        _openRunForm();
      case SirisModuleAction.logWorkout:
        _openWorkoutForm();
      case SirisModuleAction.open:
        _selectModule(module.id);
    }
  }

  Future<void> _showQuickActions() async {
    final quickActionModules = SirisModuleRegistry.supporting(
      SirisModuleCapability.quickAction,
    ).toList(growable: false);

    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Quick actions',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 14),
              _QuickActionTile(
                icon: Icons.search_rounded,
                title: 'Search SirisOS',
                onTap: () {
                  Navigator.pop(sheetContext);
                  _openSearch();
                },
              ),
              for (final module in quickActionModules)
                _QuickActionTile(
                  icon: module.selectedIcon,
                  title: module.primaryActionLabel ?? 'Open ${module.label}',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _performModuleAction(module);
                  },
                ),
              const Divider(height: 28),
              _QuickActionTile(
                icon: Icons.logout_rounded,
                title: 'Sign out',
                destructive: true,
                onTap: () async {
                  Navigator.pop(sheetContext);
                  await widget.onLogout();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 900;
        final content = IndexedStack(
          index: _selectedIndex,
          children: _navigationModules.map(_screenFor).toList(growable: false),
        );

        return Scaffold(
          body: desktop
              ? Row(
                  children: [
                    Container(
                      width: 248,
                      decoration: const BoxDecoration(
                        color: AppTheme.sidebar,
                        border: Border(
                          right: BorderSide(color: AppTheme.border),
                        ),
                      ),
                      child: SafeArea(
                        child: Column(
                          children: [
                            const Padding(
                              padding: EdgeInsets.fromLTRB(22, 24, 22, 24),
                              child: SirisLogo(size: 58),
                            ),
                            Expanded(
                              child: NavigationRail(
                                extended: true,
                                minExtendedWidth: 248,
                                selectedIndex: _selectedIndex,
                                onDestinationSelected: _selectTab,
                                labelType: NavigationRailLabelType.none,
                                destinations: _navigationModules
                                    .map(
                                      (module) => NavigationRailDestination(
                                        icon: Icon(module.icon),
                                        selectedIcon: Icon(module.selectedIcon),
                                        label: Text(module.label),
                                      ),
                                    )
                                    .toList(growable: false),
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                              child: FutureBuilder<DashboardSummary>(
                                future: _sidebarFuture,
                                builder: (context, snapshot) =>
                                    _SidebarStatus(data: snapshot.data),
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                              child: Column(
                                children: [
                                  ListTile(
                                    leading: const Icon(Icons.search_rounded),
                                    title: const Text('Search'),
                                    onTap: _openSearch,
                                  ),
                                  ListTile(
                                    leading: const Icon(Icons.logout_rounded),
                                    title: const Text('Logout'),
                                    onTap: widget.onLogout,
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    Expanded(child: content),
                  ],
                )
              : content,
          floatingActionButton: FloatingActionButton(
            onPressed: _showQuickActions,
            tooltip: 'Quick actions',
            child: const Icon(Icons.add_rounded),
          ),
          bottomNavigationBar: desktop
              ? null
              : NavigationBar(
                  selectedIndex: _selectedIndex,
                  onDestinationSelected: _selectTab,
                  destinations: _navigationModules
                      .map(
                        (module) => NavigationDestination(
                          icon: Icon(module.icon),
                          selectedIcon: Icon(module.selectedIcon),
                          label: module.label,
                        ),
                      )
                      .toList(growable: false),
                ),
        );
      },
    );
  }
}

class _SidebarStatus extends StatelessWidget {
  const _SidebarStatus({this.data});

  final DashboardSummary? data;

  @override
  Widget build(BuildContext context) {
    final dashboard = data;
    final healthy = dashboard != null &&
        dashboard.homelab.status != 'warning' &&
        dashboard.system.status != 'warning';
    final statusColor =
        healthy ? AppTheme.success : Theme.of(context).colorScheme.error;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceRaised.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'SYSTEM',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  letterSpacing: 1.2,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: statusColor,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: statusColor.withValues(alpha: 0.5),
                      blurRadius: 8,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                dashboard == null
                    ? 'Loading status'
                    : healthy
                        ? 'Healthy'
                        : 'Needs attention',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _StatusLine(
            label: 'Homelab',
            value: dashboard?.homelab.value ?? '—',
          ),
          const SizedBox(height: 7),
          _StatusLine(label: 'CPU', value: dashboard?.system.value ?? '—'),
          const SizedBox(height: 7),
          _StatusLine(
            label: 'Memory',
            value: dashboard?.system.subtitle ?? '—',
          ),
        ],
      ),
    );
  }
}

class _StatusLine extends StatelessWidget {
  const _StatusLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontSize: 12,
              ),
            ),
          ),
          Flexible(
            child: Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.right,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      );
}

class _QuickActionTile extends StatelessWidget {
  const _QuickActionTile({
    required this.icon,
    required this.title,
    required this.onTap,
    this.destructive = false,
  });

  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    final color = destructive
        ? Theme.of(context).colorScheme.error
        : Theme.of(context).colorScheme.primary;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(13),
        ),
        child: Icon(icon, color: color),
      ),
      title: Text(title),
      trailing: const Icon(Icons.chevron_right_rounded),
      onTap: onTap,
    );
  }
}

class _ComingSoonScreen extends StatelessWidget {
  const _ComingSoonScreen();

  @override
  Widget build(BuildContext context) => const SafeArea(
        child: Center(
          child: Padding(
            padding: EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SirisLogo(size: 82),
                SizedBox(height: 22),
                Text('Siris AI command centre is coming next.'),
              ],
            ),
          ),
        ),
      );
}

class _UnknownModuleScreen extends StatelessWidget {
  const _UnknownModuleScreen({required this.module});

  final SirisModuleDefinition module;

  @override
  Widget build(BuildContext context) => SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(module.selectedIcon, size: 64),
                const SizedBox(height: 18),
                Text(
                  module.label,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                Text(
                  module.description,
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      );
}
