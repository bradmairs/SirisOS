import 'package:flutter/material.dart';

import '../models/dashboard_summary.dart';
import '../services/activity_service.dart';
import '../services/dashboard_service.dart';
import '../widgets/activity_feed_panel.dart';
import '../widgets/dashboard_card.dart';
import 'notification_center_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final DashboardService _service = DashboardService();
  final ActivityService _activityService = ActivityService();
  late Future<DashboardSummary> _dashboardFuture;
  int _unreadCount = 0;

  @override
  void initState() {
    super.initState();
    _dashboardFuture = _service.fetchDashboard();
    _loadUnreadCount();
  }

  Future<void> _loadUnreadCount() async {
    try {
      final count = await _activityService.fetchUnreadCount();
      if (mounted) setState(() => _unreadCount = count);
    } catch (_) {}
  }

  Future<void> _refresh() async {
    final next = _service.fetchDashboard();
    setState(() => _dashboardFuture = next);
    await Future.wait([next, _loadUnreadCount()]);
  }

  Future<void> _openNotifications() async {
    await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(builder: (_) => const NotificationCenterScreen()),
    );
    await _loadUnreadCount();
  }

  String _greeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FutureBuilder<DashboardSummary>(
        future: _dashboardFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError || !snapshot.hasData) {
            return _ErrorState(onRetry: _refresh);
          }

          final data = snapshot.data!;
          return RefreshIndicator(
            onRefresh: _refresh,
            child: CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                  sliver: SliverToBoxAdapter(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${_greeting()}, ${data.greetingName}', style: Theme.of(context).textTheme.headlineMedium),
                              const SizedBox(height: 6),
                              Text('Your live SirisOS command centre.', style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                            ],
                          ),
                        ),
                        Stack(
                          clipBehavior: Clip.none,
                          children: [
                            IconButton.filledTonal(
                              onPressed: _openNotifications,
                              tooltip: 'Notifications',
                              icon: const Icon(Icons.notifications_rounded),
                            ),
                            if (_unreadCount > 0)
                              Positioned(
                                right: -2,
                                top: -3,
                                child: Container(
                                  constraints: const BoxConstraints(minWidth: 20, minHeight: 20),
                                  padding: const EdgeInsets.symmetric(horizontal: 5),
                                  decoration: BoxDecoration(color: Theme.of(context).colorScheme.error, borderRadius: BorderRadius.circular(999)),
                                  alignment: Alignment.center,
                                  child: Text(_unreadCount > 99 ? '99+' : '$_unreadCount', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(width: 8),
                        IconButton.filledTonal(onPressed: _refresh, tooltip: 'Refresh dashboard', icon: const Icon(Icons.refresh_rounded)),
                      ],
                    ),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.all(20),
                  sliver: SliverLayoutBuilder(
                    builder: (context, constraints) {
                      final width = constraints.crossAxisExtent;
                      final columns = width >= 1000 ? 4 : width >= 650 ? 2 : 1;
                      return SliverGrid(
                        delegate: SliverChildListDelegate.fixed([
                          _card(data.homelab, Icons.dns_rounded),
                          _card(data.running, Icons.directions_run_rounded),
                          _card(data.gym, Icons.fitness_center_rounded),
                          _card(data.system, Icons.memory_rounded),
                        ]),
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: columns, crossAxisSpacing: 16, mainAxisSpacing: 16, mainAxisExtent: 180),
                      );
                    },
                  ),
                ),
                const SliverPadding(padding: EdgeInsets.fromLTRB(20, 0, 20, 20), sliver: SliverToBoxAdapter(child: ActivityFeedPanel())),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
                  sliver: SliverToBoxAdapter(
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(22),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(children: [Icon(Icons.auto_awesome_rounded, color: Theme.of(context).colorScheme.primary), const SizedBox(width: 10), Text('SirisOS briefing', style: Theme.of(context).textTheme.titleLarge)]),
                            const SizedBox(height: 18),
                            if (data.briefingItems.isEmpty)
                              const Text('No briefing items are available yet.')
                            else
                              ...data.briefingItems.map((item) => Padding(
                                    padding: const EdgeInsets.only(bottom: 12),
                                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                      Padding(padding: const EdgeInsets.only(top: 7), child: Container(width: 6, height: 6, decoration: BoxDecoration(color: Theme.of(context).colorScheme.primary, shape: BoxShape.circle))),
                                      const SizedBox(width: 12),
                                      Expanded(child: Text(item)),
                                    ]),
                                  )),
                            Text('Updated ${TimeOfDay.fromDateTime(data.generatedAt.toLocal()).format(context)}', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  DashboardCard _card(DashboardCardData data, IconData icon) => DashboardCard(title: data.title, value: data.value, subtitle: data.subtitle, status: data.status, icon: icon);
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.onRetry});
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.cloud_off_rounded, size: 52, color: Theme.of(context).colorScheme.onSurfaceVariant),
          const SizedBox(height: 18),
          Text('SirisOS backend unavailable', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 20),
          FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: const Text('Try again')),
        ]),
      ),
    );
  }
}
