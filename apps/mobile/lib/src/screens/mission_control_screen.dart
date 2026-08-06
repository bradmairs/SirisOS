import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/mission_control_priority.dart';
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
  static const _adaptiveKey = 'mission.adaptive_layout';
  static const _secondsKey = 'mission.show_seconds';

  final DashboardService _dashboardService = DashboardService();
  final DashboardLayoutService _layoutService = DashboardLayoutService();
  final MissionControlPriorityEngine _priorityEngine =
      const MissionControlPriorityEngine();

  late Future<DashboardSummary> _dashboardFuture;
  List<DashboardWidgetPreference> _layout =
      DashboardLayoutService.defaultLayout();
  StreamSubscription<SirisEvent>? _events;
  Timer? _clockTimer;
  Timer? _refreshDebounce;
  DateTime _now = DateTime.now();
  bool _adaptiveLayout = true;
  bool _showSeconds = false;

  @override
  void initState() {
    super.initState();
    _dashboardFuture = _dashboardService.fetchDashboard();
    _loadLayout();
    _loadDisplayPreferences();
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
    if (event is MissionControlRefreshed &&
        event.source == 'dashboard_service') {
      return;
    }
    if (event is! ModuleDataChanged && event is! NotificationStateChanged) {
      return;
    }
    _refreshDebounce?.cancel();
    _refreshDebounce = Timer(const Duration(milliseconds: 350), _refresh);
  }

  Future<void> _loadLayout() async {
    final layout = await _layoutService.load();
    if (mounted) setState(() => _layout = layout);
  }

  Future<void> _loadDisplayPreferences() async {
    final preferences = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      _adaptiveLayout = preferences.getBool(_adaptiveKey) ?? true;
      _showSeconds = preferences.getBool(_secondsKey) ?? false;
    });
  }

  Future<void> _setAdaptiveLayout(bool value) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(_adaptiveKey, value);
    if (mounted) setState(() => _adaptiveLayout = value);
  }

  Future<void> _setShowSeconds(bool value) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(_secondsKey, value);
    if (mounted) setState(() => _showSeconds = value);
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    final next = _dashboardService.fetchDashboard();
    setState(() => _dashboardFuture = next);
    try {
      await next;
    } catch (_) {}
  }

  Future<void> _showDisplayControls() async {
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
                'Mission Control display',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              SwitchListTile.adaptive(
                contentPadding: EdgeInsets.zero,
                value: _adaptiveLayout,
                title: const Text('Adaptive prioritisation'),
                subtitle: const Text(
                  'Move and expand widgets that require attention without changing your saved layout.',
                ),
                onChanged: _setAdaptiveLayout,
              ),
              SwitchListTile.adaptive(
                contentPadding: EdgeInsets.zero,
                value: _showSeconds,
                title: const Text('Show clock seconds'),
                subtitle: const Text('Useful for an active operations display.'),
                onChanged: _setShowSeconds,
              ),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton(
                  onPressed: () => Navigator.pop(sheetContext),
                  child: const Text('Done'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String get _time {
    final base = '${_two(_now.hour)}:${_two(_now.minute)}';
    return _showSeconds ? '$base:${_two(_now.second)}' : base;
  }

  String get _date {
    const weekdays = [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ];
    const months = [
      'January',
      'February',
      'March',
      'April',
      'May',
      'June',
      'July',
      'August',
      'September',
      'October',
      'November',
      'December',
    ];
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
            if (snapshot.connectionState == ConnectionState.waiting &&
                !snapshot.hasData) {
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
            final visible = _priorityEngine.arrange(
              _layout,
              data,
              adaptive: _adaptiveLayout,
            );

            return LayoutBuilder(
              builder: (context, constraints) {
                final desktop = constraints.maxWidth >= 1000;
                final contentWidth = constraints.maxWidth - 48;
                const gap = 16.0;
                final columns = constraints.maxWidth >= 1400
                    ? 4
                    : desktop
                        ? 3
                        : constraints.maxWidth >= 700
                            ? 2
                            : 1;
                final unitWidth =
                    (contentWidth - gap * (columns - 1)) / columns;

                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(24, 18, 24, 32),
                    children: [
                      _SituationHeader(
                        time: _time,
                        date: _date,
                        adaptive: _adaptiveLayout,
                        onControls: _showDisplayControls,
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
                            key: ValueKey(item.id),
                            duration: const Duration(milliseconds: 300),
                            curve: Curves.easeOutCubic,
                            width: width,
                            child: AppWidgetRegistry.build(
                              item.id,
                              widgetContext,
                            ),
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
    return span >= columns
        ? contentWidth
        : unitWidth * span + gap * (span - 1);
  }
}

class _SituationHeader extends StatelessWidget {
  const _SituationHeader({
    required this.time,
    required this.date,
    required this.adaptive,
    required this.onControls,
    required this.onExit,
    required this.onRefresh,
  });

  final String time;
  final String date;
  final bool adaptive;
  final VoidCallback onControls;
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
              Row(
                children: [
                  Text(
                    'SIRIS MISSION CONTROL',
                    style: textTheme.labelLarge?.copyWith(
                      letterSpacing: 2.4,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  if (adaptive) ...[
                    const SizedBox(width: 10),
                    const Chip(
                      avatar: Icon(Icons.auto_awesome_rounded, size: 16),
                      label: Text('ADAPTIVE'),
                      visualDensity: VisualDensity.compact,
                    ),
                  ],
                ],
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
          onPressed: onControls,
          tooltip: 'Display controls',
          icon: const Icon(Icons.tune_rounded),
        ),
        const SizedBox(width: 8),
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
