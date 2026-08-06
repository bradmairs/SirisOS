import 'dart:async';

import 'package:flutter/material.dart';

import '../core/siris_event_bus.dart';
import '../core/siris_scheduler.dart';
import '../models/dashboard_summary.dart';
import '../models/mission_control_widget.dart';
import '../modules/app_widget_registry.dart';
import '../services/dashboard_layout_service.dart';
import '../services/dashboard_service.dart';

class MissionControlScreen extends StatefulWidget {
  const MissionControlScreen({super.key});

  static const routeName = '/mission';

  @override
  State<MissionControlScreen> createState() => _MissionControlScreenState();
}

class _MissionControlScreenState extends State<MissionControlScreen> {
  static const _refreshJobId = 'situation-room.refresh';
  final DashboardService _dashboardService = DashboardService();
  final DashboardLayoutService _layoutService = DashboardLayoutService();

  late Future<DashboardSummary> _dashboardFuture;
  List<DashboardWidgetPreference> _layout = DashboardLayoutService.defaultLayout();
  StreamSubscription<SirisEvent>? _events;
  Timer? _clockTimer;
  Timer? _refreshDebounce;
  DateTime _now = DateTime.now();

  @override
  void initState() {
    super.initState();
    _dashboardFuture = _dashboardService.fetchDashboard();
    _loadLayout();
    _events = SirisEventBus.instance.events.listen(_onEvent);
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _now = DateTime.now());
    });
    SirisScheduler.instance.register(
      SirisScheduledJob(
        id: _refreshJobId,
        interval: const Duration(minutes: 5),
        run: _refresh,
      ),
    );
  }

  @override
  void dispose() {
    _events?.cancel();
    _clockTimer?.cancel();
    _refreshDebounce?.cancel();
    SirisScheduler.instance.unregister(_refreshJobId);
    super.dispose();
  }

  void _onEvent(SirisEvent event) {
    if (event is MissionControlRefreshed && event.source == 'dashboard_service') return;
    if (event is! ModuleDataChanged && event is! NotificationStateChanged) return;
    _refreshDebounce?.cancel();
    _refreshDebounce = Timer(const Duration(milliseconds: 350), _refresh);
  }

  Future<void> _loadLayout() async {
    final layout = await _layoutService.load();
    if (mounted) setState(() => _layout = layout);
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    final next = _dashboardService.fetchDashboard();
    setState(() => _dashboardFuture = next);
    try {
      await next;
    } catch (_) {}
  }

  String get _time => '${_two(_now.hour)}:${_two(_now.minute)}';

  String get _date {
    const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    return '${weekdays[_now.weekday - 1]}, ${_now.day} ${months[_now.month - 1]} ${_now.year}';
  }

  String get _greeting => _now.hour < 12
      ? 'Good morning'
      : _now.hour < 18
          ? 'Good afternoon'
          : 'Good evening';

  static String _two(int value) => value.toString().padLeft(2, '0');

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: FutureBuilder<DashboardSummary>(
          future: _dashboardFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting && !snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            if (!snapshot.hasData) {
              return Center(
                child: FilledButton.icon(
                  onPressed: _refresh,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Retry Mission Control'),
                ),
              );
            }

            final data = snapshot.data!;
            final widgetContext = MissionControlWidgetContext(
              dashboard: data,
              greeting: _greeting,
            );
            final visible = _layout.where((item) => item.visible).toList(growable: false);

            return LayoutBuilder(
              builder: (context, constraints) {
                final desktop = constraints.maxWidth >= 1000;
                final contentWidth = constraints.maxWidth - 48;
                const gap = 16.0;
                final columns = constraints.maxWidth >= 1400 ? 4 : desktop ? 3 : constraints.maxWidth >= 700 ? 2 : 1;
                final unitWidth = (contentWidth - gap * (columns - 1)) / columns;

                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(24, 18, 24, 32),
                    children: [
                      _SituationHeader(
                        time: _time,
                        date: _date,
                        onExit: () => Navigator.of(context).maybePop(),
                        onRefresh: _refresh,
                      ),
                      const SizedBox(height: 20),
                      Wrap(
                        spacing: gap,
                        runSpacing: gap,
                        children: visible.map((item) {
                          final width = _widthFor(
                            item.size,
                            columns,
                            unitWidth,
                            gap,
                            contentWidth,
                          );
                          return AnimatedContainer(
                            duration: const Duration(milliseconds: 300),
                            curve: Curves.easeOutCubic,
                            width: width,
                            child: AppWidgetRegistry.build(item.id, widgetContext),
                          );
                        }).toList(growable: false),
                      ),
                    ],
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }

  static double _widthFor(
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
    return span >= columns ? contentWidth : unitWidth * span + gap * (span - 1);
  }
}

class _SituationHeader extends StatelessWidget {
  const _SituationHeader({
    required this.time,
    required this.date,
    required this.onExit,
    required this.onRefresh,
  });

  final String time;
  final String date;
  final VoidCallback onExit;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'SIRIS MISSION CONTROL',
                style: textTheme.labelLarge?.copyWith(
                  letterSpacing: 2.4,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                time,
                style: textTheme.displayLarge?.copyWith(
                  fontWeight: FontWeight.w300,
                  height: 0.95,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                date,
                style: textTheme.titleMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        IconButton.filledTonal(
          onPressed: onRefresh,
          tooltip: 'Refresh',
          icon: const Icon(Icons.refresh_rounded),
        ),
        const SizedBox(width: 8),
        IconButton.filledTonal(
          onPressed: onExit,
          tooltip: 'Exit Mission Control',
          icon: const Icon(Icons.close_fullscreen_rounded),
        ),
      ],
    );
  }
}
