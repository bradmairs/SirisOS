import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/module_registry.dart';
import '../models/dashboard_summary.dart';
import '../modules/app_module_registry.dart';
import '../services/dashboard_service.dart';
import '../theme/app_theme.dart';
import '../widgets/command_palette_dialog.dart';
import '../widgets/siris_logo.dart';
import 'global_search_screen.dart';
import 'mission_control_screen.dart';
import 'notification_center_screen.dart';
import 'operations_center_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({required this.onLogout, super.key});

  final Future<void> Function() onLogout;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  static const _mobilePrimaryModuleIds = <String>[
    'dashboard',
    'homelab',
    'running',
    'gym',
    'health',
    'engineering',
  ];

  final DashboardService _dashboardService = DashboardService();
  final List<SirisModuleRegistration> _navigationModules =
      AppModuleRegistry.registrations;

  int _selectedIndex = 0;
  int _runAddRequest = 0;
  int _workoutAddRequest = 0;
  late Future<DashboardSummary> _sidebarFuture;

  @override
  void initState() {
    super.initState();
    _sidebarFuture = _dashboardService.fetchDashboard();
    HardwareKeyboard.instance.addHandler(_handleGlobalKey);
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_handleGlobalKey);
    super.dispose();
  }

  bool _handleGlobalKey(KeyEvent event) {
    if (event is! KeyDownEvent) return false;
    if (event.logicalKey != LogicalKeyboardKey.keyK) return false;
    if (!HardwareKeyboard.instance.isControlPressed &&
        !HardwareKeyboard.instance.isMetaPressed) {
      return false;
    }
    _openCommandPalette();
    return true;
  }

  void _selectTab(int index) => setState(() => _selectedIndex = index);

  void _selectModule(String moduleId) {
    final index = AppModuleRegistry.navigationIndexOf(moduleId);
    if (index >= 0) _selectTab(index);
  }

  void _openRunForm() => setState(() {
        _selectedIndex = AppModuleRegistry.navigationIndexOf('running');
        _runAddRequest++;
      });

  void _openWorkoutForm() => setState(() {
        _selectedIndex = AppModuleRegistry.navigationIndexOf('gym');
        _workoutAddRequest++;
      });

  Future<void> _openMissionControl() =>
      Navigator.of(context).pushNamed(MissionControlScreen.routeName);

  Future<void> _openOperationsCenter() =>
      Navigator.of(context).pushNamed(OperationsCenterScreen.routeName);

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

  void _openCommandPalette() {
    showCommandPalette(context: context, onOpenTarget: _openSearchTarget);
  }

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
    final quickActionModules = _navigationModules
        .where(
          (registration) =>
              registration.isAvailable &&
              registration.definition.supports(
                SirisModuleCapability.quickAction,
              ),
        )
        .map((registration) => registration.definition)
        .toList(growable: false);

    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      useSafeArea: true,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Quick actions',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 14),
            _QuickActionTile(
              icon: Icons.monitor_heart_rounded,
              title: 'Open Mission Control',
              onTap: () {
                Navigator.pop(sheetContext);
                _openMissionControl();
              },
            ),
            _QuickActionTile(
              icon: Icons.radar_rounded,
              title: 'Open Operations Center',
              onTap: () {
                Navigator.pop(sheetContext);
                _openOperationsCenter();
              },
            ),
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
    );
  }

  Future<void> _showMoreMenu() async {
    final secondaryModules = _navigationModules
        .where(
          (registration) =>
              !_mobilePrimaryModuleIds.contains(registration.definition.id),
        )
        .toList(growable: false);

    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (sheetContext) => SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 2, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('More', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 6),
            Text(
              'Additional SirisOS modules and system tools.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 18),
            for (final registration in secondaryModules)
              _QuickActionTile(
                icon: registration.definition.selectedIcon,
                title: registration.definition.label,
                onTap: () {
                  Navigator.pop(sheetContext);
                  _selectModule(registration.definition.id);
                },
              ),
            const Divider(height: 28),
            _QuickActionTile(
              icon: Icons.monitor_heart_rounded,
              title: 'Mission Control',
              onTap: () {
                Navigator.pop(sheetContext);
                _openMissionControl();
              },
            ),
            _QuickActionTile(
              icon: Icons.radar_rounded,
              title: 'Operations Center',
              onTap: () {
                Navigator.pop(sheetContext);
                _openOperationsCenter();
              },
            ),
            _QuickActionTile(
              icon: Icons.search_rounded,
              title: 'Search SirisOS',
              onTap: () {
                Navigator.pop(sheetContext);
                _openSearch();
              },
            ),
            _QuickActionTile(
              icon: Icons.notifications_rounded,
              title: 'Notifications',
              onTap: () {
                Navigator.pop(sheetContext);
                _openSearchTarget('notifications');
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
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 900;
        final screenContext = SirisModuleScreenContext(
          runAddRequest: _runAddRequest,
          workoutAddRequest: _workoutAddRequest,
        );
        final content = IndexedStack(
          index: _selectedIndex,
          children: _navigationModules
              .map((registration) => registration.buildScreen(screenContext))
              .toList(growable: false),
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
                                      (registration) =>
                                          NavigationRailDestination(
                                        icon:
                                            Icon(registration.definition.icon),
                                        selectedIcon: Icon(
                                          registration.definition.selectedIcon,
                                        ),
                                        label:
                                            Text(registration.definition.label),
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
                                    leading: const Icon(
                                      Icons.monitor_heart_rounded,
                                    ),
                                    title: const Text('Mission Control'),
                                    onTap: _openMissionControl,
                                  ),
                                  ListTile(
                                    leading: const Icon(Icons.radar_rounded),
                                    title: const Text('Operations Center'),
                                    onTap: _openOperationsCenter,
                                  ),
                                  ListTile(
                                    leading: const Icon(Icons.search_rounded),
                                    title: const Text('Search'),
                                    trailing: Text(
                                      '⌘K',
                                      style: Theme.of(context)
                                          .textTheme
                                          .labelSmall
                                          ?.copyWith(
                                            color: Theme.of(context)
                                                .colorScheme
                                                .onSurfaceVariant,
                                          ),
                                    ),
                                    onTap: _openCommandPalette,
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
              : _MobileBottomNavigation(
                  registrations: _navigationModules,
                  selectedIndex: _selectedIndex,
                  primaryModuleIds: _mobilePrimaryModuleIds,
                  onSelectModule: _selectModule,
                  onMore: _showMoreMenu,
                ),
        );
      },
    );
  }
}

class _MobileBottomNavigation extends StatelessWidget {
  const _MobileBottomNavigation({
    required this.registrations,
    required this.selectedIndex,
    required this.primaryModuleIds,
    required this.onSelectModule,
    required this.onMore,
  });

  final List<SirisModuleRegistration> registrations;
  final int selectedIndex;
  final List<String> primaryModuleIds;
  final ValueChanged<String> onSelectModule;
  final VoidCallback onMore;

  @override
  Widget build(BuildContext context) {
    final primary = primaryModuleIds
        .map(AppModuleRegistry.find)
        .whereType<SirisModuleRegistration>()
        .toList(growable: false);
    final selectedId =
        selectedIndex >= 0 && selectedIndex < registrations.length
            ? registrations[selectedIndex].definition.id
            : null;
    final moreSelected =
        selectedId != null && !primaryModuleIds.contains(selectedId);

    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppTheme.sidebar,
        border: Border(top: BorderSide(color: AppTheme.border)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 68,
          child: Row(
            children: [
              for (final registration in primary)
                Expanded(
                  child: _MobileNavItem(
                    icon: registration.definition.icon,
                    selectedIcon: registration.definition.selectedIcon,
                    label: registration.definition.label,
                    selected: selectedId == registration.definition.id,
                    onTap: () => onSelectModule(registration.definition.id),
                  ),
                ),
              Expanded(
                child: _MobileNavItem(
                  icon: Icons.more_horiz_rounded,
                  selectedIcon: Icons.more_horiz_rounded,
                  label: 'More',
                  selected: moreSelected,
                  onTap: onMore,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MobileNavItem extends StatelessWidget {
  const _MobileNavItem({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = selected
        ? theme.colorScheme.primary
        : theme.colorScheme.onSurfaceVariant;

    return InkResponse(
      onTap: onTap,
      radius: 32,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(2, 7, 2, 5),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 4),
              decoration: BoxDecoration(
                color: selected
                    ? theme.colorScheme.primary.withValues(alpha: 0.15)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(18),
              ),
              child: Icon(
                selected ? selectedIcon : icon,
                size: 23,
                color: color,
              ),
            ),
            const SizedBox(height: 2),
            SizedBox(
              height: 15,
              width: double.infinity,
              child: FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.center,
                child: Text(
                  label,
                  maxLines: 1,
                  softWrap: false,
                  style: TextStyle(
                    color: color,
                    fontSize: 10.5,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
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
