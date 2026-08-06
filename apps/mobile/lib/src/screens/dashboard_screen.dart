import 'dart:async';

import 'package:flutter/material.dart';

import '../core/siris_event_bus.dart';
import '../core/siris_scheduler.dart';
import '../models/dashboard_summary.dart';
import '../models/mission_control_widget.dart';
import '../modules/app_widget_registry.dart';
import '../services/activity_service.dart';
import '../services/dashboard_layout_service.dart';
import '../services/dashboard_service.dart';
import 'notification_center_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  static const _refreshJobId = 'mission-control.refresh';

  final DashboardService _service = DashboardService();
  final ActivityService _activityService = ActivityService();
  final DashboardLayoutService _layoutService = DashboardLayoutService();

  late Future<DashboardSummary> _dashboardFuture;
  StreamSubscription<SirisEvent>? _eventSubscription;
  Timer? _eventDebounce;
  List<DashboardWidgetPreference> _layout = DashboardLayoutService.defaultLayout();
  int _unreadCount = 0;

  @override
  void initState() {
    super.initState();
    _dashboardFuture = _service.fetchDashboard();
    _loadUnreadCount();
    _loadLayout();
    _eventSubscription = SirisEventBus.instance.events.listen(_handleEvent);
    SirisScheduler.instance.register(
      SirisScheduledJob(
        id: _refreshJobId,
        interval: const Duration(minutes: 5),
        run: _refreshSilently,
      ),
    );
  }

  @override
  void dispose() {
    _eventDebounce?.cancel();
    _eventSubscription?.cancel();
    SirisScheduler.instance.unregister(_refreshJobId);
    super.dispose();
  }

  void _handleEvent(SirisEvent event) {
    if (event is MissionControlRefreshed && event.source == 'dashboard_service') return;
    if (event is! ModuleDataChanged && event is! NotificationStateChanged) return;
    _eventDebounce?.cancel();
    _eventDebounce = Timer(const Duration(milliseconds: 350), _refreshSilently);
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

  Future<void> _refreshSilently() async {
    if (!mounted) return;
    final next = _service.fetchDashboard();
    setState(() => _dashboardFuture = next);
    try {
      await Future.wait([next, _loadUnreadCount()]);
    } catch (_) {}
  }

  Future<void> _refresh() => _refreshSilently();

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
                Text('Customise Mission Control', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 6),
                Text(
                  'Reorder, resize or hide the panels in your workspace.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 430,
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
                      final definition = AppWidgetRegistry.definitionFor(item.id);
                      return Card(
                        key: ValueKey(item.id),
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          leading: Icon(definition.icon),
                          title: Text(definition.label),
                          subtitle: Text('${definition.moduleId} · ${_sizeLabel(item.size)}'),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              DropdownButton<MissionControlWidgetSize>(
                                value: item.size,
                                underline: const SizedBox.shrink(),
                                items: MissionControlWidgetSize.values
                                    .map((size) => DropdownMenuItem(value: size, child: Text(_sizeLabel(size))))
                                    .toList(),
                                onChanged: (size) {
                                  if (size == null) return;
                                  setModalState(() => draft[index] = item.copyWith(size: size));
                                },
                              ),
                              Switch(
                                value: item.visible,
                                onChanged: (visible) => setModalState(
                                  () => draft[index] = item.copyWith(visible: visible),
                                ),
                              ),
                              ReorderableDragStartListener(
                                index: index,
                                child: const Icon(Icons.drag_handle_rounded),
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
                        setModalState(() => draft = DashboardLayoutService.defaultLayout());
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
          if (snapshot.hasError || !snapshot.hasData) return _ErrorState(onRetry: _refresh);

          final data = snapshot.data!;
          final widgetContext = MissionControlWidgetContext(dashboard: data, greeting: _greeting());
          return RefreshIndicator(
            onRefresh: _refresh,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final contentWidth = constraints.maxWidth - 40;
                const gap = 16.0;
                final columns = constraints.maxWidth >= 1180 ? 4 : constraints.maxWidth >= 720 ? 2 : 1;
                final unitWidth = (contentWidth - (gap * (columns - 1))) / columns;
                return ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
                  children: [
                    _header(),
                    const SizedBox(height: 18),
                    Wrap(
                      spacing: gap,
                      runSpacing: gap,
                      children: _layout.where((item) => item.visible).map(
                        (item) => SizedBox(
                          width: _widgetWidth(item.size, columns, unitWidth, gap, contentWidth),
                          child: AppWidgetRegistry.build(item.id, widgetContext),
                        ),
                      ).toList(),
                    ),
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }

  Widget _header() => Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Mission Control', style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 5),
                Text(
                  'Your live, configurable SirisOS workspace.',
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
              ],
            ),
          ),
          IconButton.filledTonal(
            onPressed: _editLayout,
            tooltip: 'Customise Mission Control',
            icon: const Icon(Icons.dashboard_customize_rounded),
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
            tooltip: 'Refresh Mission Control',
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      );

  static double _widgetWidth(
    MissionControlWidgetSize size,
    int columns,
    double unitWidth,
    double gap,
    double contentWidth,
  ) {
    if (columns == 1) return contentWidth;
    final span = switch (size) {
      MissionControlWidgetSize.compact => 1,
      MissionControlWidgetSize.standard => 1,
      MissionControlWidgetSize.wide => columns,
    };
    return span >= columns ? contentWidth : (unitWidth * span) + (gap * (span - 1));
  }

  static String _sizeLabel(MissionControlWidgetSize size) => switch (size) {
        MissionControlWidgetSize.compact => 'Compact',
        MissionControlWidgetSize.standard => 'Standard',
        MissionControlWidgetSize.wide => 'Wide',
      };
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.onRetry});

  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) => Center(
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
