import 'package:flutter/material.dart';

import '../models/dashboard_summary.dart';
import '../services/activity_service.dart';
import '../services/dashboard_layout_service.dart';
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
            padding: EdgeInsets.fromLTRB(
              20,
              0,
              20,
              20 + MediaQuery.viewInsetsOf(context).bottom,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Customise Dashboard', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 6),
                Text(
                  'Drag widgets into your preferred order and hide anything you do not need.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 410,
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
                          subtitle: Text(_widgetDescription(item.id)),
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
          final visibleWidgets = _layout.where((item) => item.visible).toList();
          return RefreshIndicator(
            onRefresh: _refresh,
            child: CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                  sliver: SliverToBoxAdapter(child: _header(data)),
                ),
                if (visibleWidgets.isEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.all(20),
                    sliver: SliverToBoxAdapter(
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(28),
                          child: Column(
                            children: [
                              const Icon(Icons.dashboard_customize_rounded, size: 44),
                              const SizedBox(height: 12),
                              const Text('All dashboard widgets are hidden.'),
                              const SizedBox(height: 14),
                              FilledButton.icon(
                                onPressed: _editLayout,
                                icon: const Icon(Icons.tune_rounded),
                                label: const Text('Customise Dashboard'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  )
                else
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
                    sliver: SliverList.separated(
                      itemCount: visibleWidgets.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 16),
                      itemBuilder: (context, index) =>
                          _buildWidget(visibleWidgets[index].id, data),
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _header(DashboardSummary data) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${_greeting()}, ${data.greetingName}',
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 6),
              Text('Your live SirisOS command centre.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
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

  Widget _buildWidget(String id, DashboardSummary data) {
    return switch (id) {
      'homelab' => SizedBox(height: 180, child: _card(data.homelab, Icons.dns_rounded)),
      'running' => SizedBox(
          height: 180,
          child: _card(data.running, Icons.directions_run_rounded),
        ),
      'gym' => SizedBox(
          height: 180,
          child: _card(data.gym, Icons.fitness_center_rounded),
        ),
      'system' => SizedBox(height: 180, child: _card(data.system, Icons.memory_rounded)),
      'activity' => const ActivityFeedPanel(),
      'briefing' => _briefingCard(data),
      _ => const SizedBox.shrink(),
    };
  }

  Widget _briefingCard(DashboardSummary data) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.auto_awesome_rounded,
                    color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 10),
                Text('SirisOS briefing', style: Theme.of(context).textTheme.titleLarge),
              ],
            ),
            const SizedBox(height: 18),
            if (data.briefingItems.isEmpty)
              const Text('No briefing items are available yet.')
            else
              ...data.briefingItems.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(top: 7),
                        child: Container(
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.primary,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(child: Text(item)),
                    ],
                  ),
                ),
              ),
            Text(
              'Updated ${TimeOfDay.fromDateTime(data.generatedAt.toLocal()).format(context)}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
      ),
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

  static String _widgetDescription(String id) => switch (id) {
        'homelab' => 'Docker health and container status',
        'running' => 'Fitness score and weekly distance',
        'gym' => 'Sessions and weekly lifting volume',
        'system' => 'Live CPU and memory usage',
        'activity' => 'Cross-module event feed',
        'briefing' => 'Rule-based daily summary',
        _ => '',
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
            Icon(Icons.cloud_off_rounded,
                size: 52, color: Theme.of(context).colorScheme.onSurfaceVariant),
            const SizedBox(height: 18),
            Text('SirisOS backend unavailable',
                style: Theme.of(context).textTheme.titleLarge),
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
