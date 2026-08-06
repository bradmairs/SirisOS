import 'package:flutter/material.dart';

import 'dashboard_screen.dart';
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

  static const _screens = <Widget>[
    DashboardScreen(),
    HomelabScreen(),
    RunningScreen(),
    GymScreen(),
    _ComingSoonScreen(
      title: 'Siris',
      message: 'Your personal AI command centre will live here.',
      icon: Icons.auto_awesome_rounded,
    ),
  ];

  void _selectTab(int index) {
    setState(() => _selectedIndex = index);
  }

  Future<void> _showQuickActions() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Quick actions', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 6),
                Text(
                  'Jump straight to the part of SirisOS you need.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 18),
                _QuickActionTile(
                  icon: Icons.directions_run_rounded,
                  title: 'Log a run',
                  subtitle: 'Open Running and add a new activity',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _selectTab(2);
                  },
                ),
                _QuickActionTile(
                  icon: Icons.fitness_center_rounded,
                  title: 'Log a workout',
                  subtitle: 'Open Gym and record your session',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _selectTab(3);
                  },
                ),
                _QuickActionTile(
                  icon: Icons.dns_rounded,
                  title: 'Open Homelab',
                  subtitle: 'Check containers, alerts and host metrics',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _selectTab(1);
                  },
                ),
                _QuickActionTile(
                  icon: Icons.notifications_rounded,
                  title: 'Notifications',
                  subtitle: 'Review recent SirisOS events and alerts',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    Navigator.of(context).push<void>(
                      MaterialPageRoute<void>(
                        builder: (_) => const NotificationCenterScreen(),
                      ),
                    );
                  },
                ),
                _QuickActionTile(
                  icon: Icons.auto_awesome_rounded,
                  title: 'Open Siris',
                  subtitle: 'AI command centre placeholder',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _selectTab(4);
                  },
                ),
                const Divider(height: 28),
                _QuickActionTile(
                  icon: Icons.logout_rounded,
                  title: 'Sign out',
                  subtitle: 'End this SirisOS session',
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
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _selectedIndex, children: _screens),
      floatingActionButton: FloatingActionButton(
        onPressed: _showQuickActions,
        tooltip: 'Quick actions',
        child: const Icon(Icons.add_rounded),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _selectTab,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard_rounded),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.dns_outlined),
            selectedIcon: Icon(Icons.dns_rounded),
            label: 'Homelab',
          ),
          NavigationDestination(
            icon: Icon(Icons.directions_run_outlined),
            selectedIcon: Icon(Icons.directions_run_rounded),
            label: 'Running',
          ),
          NavigationDestination(
            icon: Icon(Icons.fitness_center_outlined),
            selectedIcon: Icon(Icons.fitness_center_rounded),
            label: 'Gym',
          ),
          NavigationDestination(
            icon: Icon(Icons.auto_awesome_outlined),
            selectedIcon: Icon(Icons.auto_awesome_rounded),
            label: 'Siris',
          ),
        ],
      ),
    );
  }
}

class _QuickActionTile extends StatelessWidget {
  const _QuickActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.destructive = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
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
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Icon(icon, color: color),
      ),
      title: Text(title),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_right_rounded),
      onTap: onTap,
    );
  }
}

class _ComingSoonScreen extends StatelessWidget {
  const _ComingSoonScreen({
    required this.title,
    required this.message,
    required this.icon,
  });

  final String title;
  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 58, color: Theme.of(context).colorScheme.primary),
              const SizedBox(height: 20),
              Text(title, style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 10),
              Text(
                message,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
