import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/siris_logo.dart';
import 'dashboard_screen.dart';
import 'global_search_screen.dart';
import 'gym_screen.dart';
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
  int _selectedIndex = 0;
  int _runAddRequest = 0;
  int _workoutAddRequest = 0;

  void _selectTab(int index) => setState(() => _selectedIndex = index);

  void _openRunForm() => setState(() {
        _selectedIndex = 2;
        _runAddRequest++;
      });

  void _openWorkoutForm() => setState(() {
        _selectedIndex = 3;
        _workoutAddRequest++;
      });

  void _openSearchTarget(String target) {
    if (target == 'homelab') _selectTab(1);
    if (target == 'running') _selectTab(2);
    if (target == 'gym') _selectTab(3);
    if (target == 'notifications') {
      Navigator.of(context).push<void>(
        MaterialPageRoute<void>(builder: (_) => const NotificationCenterScreen()),
      );
    }
  }

  Future<void> _openSearch() => Navigator.of(context).push<void>(
        MaterialPageRoute<void>(
          builder: (_) => GlobalSearchScreen(onOpenTarget: _openSearchTarget),
        ),
      );

  List<Widget> get _screens => [
        const DashboardScreen(),
        const HomelabScreen(),
        RunningScreen(addRequest: _runAddRequest),
        GymScreen(addRequest: _workoutAddRequest),
        const _ComingSoonScreen(),
      ];

  Future<void> _showQuickActions() async {
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
              Text('Quick actions', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 14),
              _QuickActionTile(icon: Icons.search_rounded, title: 'Search SirisOS', onTap: () { Navigator.pop(sheetContext); _openSearch(); }),
              _QuickActionTile(icon: Icons.directions_run_rounded, title: 'Log a run', onTap: () { Navigator.pop(sheetContext); _openRunForm(); }),
              _QuickActionTile(icon: Icons.fitness_center_rounded, title: 'Log a workout', onTap: () { Navigator.pop(sheetContext); _openWorkoutForm(); }),
              _QuickActionTile(icon: Icons.dns_rounded, title: 'Open Homelab', onTap: () { Navigator.pop(sheetContext); _selectTab(1); }),
              const Divider(height: 28),
              _QuickActionTile(icon: Icons.logout_rounded, title: 'Sign out', destructive: true, onTap: () async { Navigator.pop(sheetContext); await widget.onLogout(); }),
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
        final content = IndexedStack(index: _selectedIndex, children: _screens);

        return Scaffold(
          body: desktop
              ? Row(
                  children: [
                    Container(
                      width: 238,
                      decoration: const BoxDecoration(
                        color: AppTheme.sidebar,
                        border: Border(right: BorderSide(color: AppTheme.border)),
                      ),
                      child: SafeArea(
                        child: Column(
                          children: [
                            const Padding(
                              padding: EdgeInsets.fromLTRB(22, 24, 22, 28),
                              child: SirisLogo(size: 58),
                            ),
                            Expanded(
                              child: NavigationRail(
                                extended: true,
                                minExtendedWidth: 238,
                                selectedIndex: _selectedIndex,
                                onDestinationSelected: _selectTab,
                                labelType: NavigationRailLabelType.none,
                                destinations: const [
                                  NavigationRailDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard_rounded), label: Text('Dashboard')),
                                  NavigationRailDestination(icon: Icon(Icons.dns_outlined), selectedIcon: Icon(Icons.dns_rounded), label: Text('Homelab')),
                                  NavigationRailDestination(icon: Icon(Icons.directions_run_outlined), selectedIcon: Icon(Icons.directions_run_rounded), label: Text('Running')),
                                  NavigationRailDestination(icon: Icon(Icons.fitness_center_outlined), selectedIcon: Icon(Icons.fitness_center_rounded), label: Text('Gym')),
                                  NavigationRailDestination(icon: Icon(Icons.auto_awesome_outlined), selectedIcon: Icon(Icons.auto_awesome_rounded), label: Text('Siris')),
                                ],
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                children: [
                                  ListTile(leading: const Icon(Icons.search_rounded), title: const Text('Search'), onTap: _openSearch),
                                  ListTile(leading: const Icon(Icons.logout_rounded), title: const Text('Logout'), onTap: widget.onLogout),
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
                  destinations: const [
                    NavigationDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard_rounded), label: 'Dashboard'),
                    NavigationDestination(icon: Icon(Icons.dns_outlined), selectedIcon: Icon(Icons.dns_rounded), label: 'Homelab'),
                    NavigationDestination(icon: Icon(Icons.directions_run_outlined), selectedIcon: Icon(Icons.directions_run_rounded), label: 'Running'),
                    NavigationDestination(icon: Icon(Icons.fitness_center_outlined), selectedIcon: Icon(Icons.fitness_center_rounded), label: 'Gym'),
                    NavigationDestination(icon: Icon(Icons.auto_awesome_outlined), selectedIcon: Icon(Icons.auto_awesome_rounded), label: 'Siris'),
                  ],
                ),
        );
      },
    );
  }
}

class _QuickActionTile extends StatelessWidget {
  const _QuickActionTile({required this.icon, required this.title, required this.onTap, this.destructive = false});
  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    final color = destructive ? Theme.of(context).colorScheme.error : Theme.of(context).colorScheme.primary;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(13)),
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
