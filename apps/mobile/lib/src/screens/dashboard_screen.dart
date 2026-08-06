import 'package:flutter/material.dart';

import '../models/dashboard_summary.dart';
import '../services/activity_service.dart';
import '../services/dashboard_layout_service.dart';
import '../services/dashboard_service.dart';
import '../widgets/activity_feed_panel.dart';
import '../widgets/dashboard_card.dart';
import '../widgets/dashboard_hero.dart';
import 'notification_center_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final DashboardService _service = DashboardService();
  final ActivityService _activityService = ActivityService();
  final DashboardLayoutService _layoutService = DashboardLayoutService();

  late Future<DashboardSummary> _dashboardFuture;
  List<DashboardWidgetPreference> _layout = DashboardLayoutService.defaultOrder
      .map((id) => DashboardWidgetPreference(id: id, visible: true))
      .toList();
  int _unreadCount = 0;

  @override
  void initState() {
    super.initState();
    _dashboardFuture = _service.fetchDashboard();
    _loadUnreadCount();
    _loadLayout();
  }

  Future<void> _loadLayout() async {
    final layout = await _layoutService.load();
    if (mounted) setState(() => _layout = layout);
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

  Future<void> _editLayout() async {
    var draft = List<DashboardWidgetPreference>.from(_layout);
    final result = await showModalBottomSheet<List<DashboardWidgetPreference>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setModalState) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Customise Dashboard', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 6),
                Text(
                  'Choose which command-centre panels are visible.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 390,
                  child: ReorderableListView.builder(
                    buildDefaultDragHandles: false,
                    itemCount: draft.length,
                    onReorder: (oldIndex, newIndex) {
                      setModalState(() {
                        if (newIndex > oldIndex) newIndex -= 1;
                        final item = draft.removeAt(oldIndex);
                        draft.insert(newIndex, item);
                      });
                    },
                    itemBuilder: (context, index) {
                      final item = draft[index];
                      return Card(
                        key: ValueKey(item.id),
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          leading: Icon(_widgetIcon(item.id)),
                          title: Text(_widgetLabel(item.id)),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Switch(
                                value: item.visible,
                                onChanged: (visible) => setModalState(
                                  () => draft[index] = item.copyWith(visible: visible),
                                ),
                              ),
                              ReorderableDragStartListener(
                                index: index,
                                child: const Padding(
                                  padding: EdgeInsets.all(8),
                                  child: Icon(Icons.drag_handle_rounded),
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    TextButton.icon(
                      onPressed: () async {
                        await _layoutService.reset();
                        setModalState(() {
                          draft = DashboardLayoutService.defaultOrder
                              .map((id) => DashboardWidgetPreference(id: id, visible: true))
                              .toList();
                        });
                      },
                      icon: const Icon(Icons.restore_rounded),
                      label: const Text('Reset'),
                    ),
                    const Spacer(),
                    FilledButton(
                      onPressed: () => Navigator.pop(context, draft),
                      child: const Text('Save layout'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );

    if (result == null) return;
    await _layoutService.save(result);
    if (mounted) setState(() => _layout = result);
  }

  String _greeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  }

  bool _visible(String id) => _layout.any((item) => item.id == id && item.visible);

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
            child: LayoutBuilder(
              builder: (context, constraints) {
                final desktop = constraints.maxWidth >= 980;
                final cardWidth = desktop
                    ? (constraints.maxWidth - 40 - 48) / 4
                    : constraints.maxWidth >= 640
                        ? (constraints.maxWidth - 40 - 16) / 2
                        : constraints.maxWidth - 40;

                return ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
                  children: [
                    _header(),
                    const SizedBox(height: 18),
                    if (_visible('briefing')) DashboardHero(greeting: _greeting(), data: data),
                    if (_visible('briefing')) const SizedBox(height: 18),
                    Wrap(
                      spacing: 16,
                      runSpacing: 16,
                      children: [
                        if (_visible('homelab')) SizedBox(width: cardWidth, height: 176, child: _card(data.homelab, Icons.dns_rounded)),
                        if (_visible('running')) SizedBox(width: cardWidth, height: 176, child: _card(data.running, Icons.directions_run_rounded)),
                        if (_visible('gym')) SizedBox(width: cardWidth, height: 176, child: _card(data.gym, Icons.fitness_center_rounded)),
                        if (_visible('system')) SizedBox(width: cardWidth, height: 176, child: _card(data.system, Icons.memory_rounded)),
                      ],
                    ),
                    if (_visible('activity')) ...[
                      const SizedBox(height: 18),
                      const ActivityFeedPanel(),
                    ],
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }

  Widget _header() {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Dashboard', style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 5),
              Text('Your live SirisOS command centre.', style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
            ],
          ),
        ),
        IconButton.filledTonal(
          onPressed: _editLayout,
          tooltip: 'Customise dashboard',
          icon: const Icon(Icons.tune_rounded),
        ),
        const SizedBox(width: 8),
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
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.error,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    _unreadCount > 99 ? '99+' : '$_unreadCount',
                    style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(width: 8),
        IconButton.filledTonal(
          onPressed: _refresh,
          tooltip: 'Refresh dashboard',
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    );
  }

  DashboardCard _card(DashboardCardData data, IconData icon) => DashboardCard(
        title: data.title,
        value: data.value,
        subtitle: data.subtitle,
        status: data.status,
        icon: icon,
      );

  static String _widgetLabel(String id) => switch (id) {
        'homelab' => 'Homelab',
        'running' => 'Running',
        'gym' => 'Gym',
        'system' => 'Server',
        'activity' => 'Recent activity',
        'briefing' => 'SirisOS briefing',
        _ => id,
      };

  static IconData _widgetIcon(String id) => switch (id) {
        'homelab' => Icons.dns_rounded,
        'running' => Icons.directions_run_rounded,
        'gym' => Icons.fitness_center_rounded,
        'system' => Icons.memory_rounded,
        'activity' => Icons.history_rounded,
        'briefing' => Icons.auto_awesome_rounded,
        _ => Icons.widgets_rounded,
      };
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.onRetry});

  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off_rounded, size: 52, color: Theme.of(context).colorScheme.onSurfaceVariant),
            const SizedBox(height: 18),
            Text('SirisOS backend unavailable', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
