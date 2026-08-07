import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/mission_control_diagnostics.dart';
import '../core/mission_control_priority.dart';
import '../core/siris_event_bus.dart';
import '../core/siris_scheduler.dart';
import '../models/dashboard_summary.dart';
import '../models/mission_control_widget.dart';
import '../modules/app_widget_registry.dart';
import '../services/dashboard_layout_service.dart';
import '../services/dashboard_service.dart';

enum MissionControlProfile { balanced, operations, compact }

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
  static const _profileKey = 'mission.display_profile';

  final DashboardService _dashboardService = DashboardService();
  final DashboardLayoutService _layoutService = DashboardLayoutService();
  final MissionControlPriorityEngine _priorityEngine =
      const MissionControlPriorityEngine();
  final MissionControlDiagnostics _diagnostics = MissionControlDiagnostics();

  late Future<DashboardSummary> _dashboardFuture;
  List<DashboardWidgetPreference> _layout =
      DashboardLayoutService.defaultLayout();
  StreamSubscription<SirisEvent>? _events;
  Timer? _clockTimer;
  Timer? _refreshDebounce;
  Timer? _wakeTimer;
  DateTime _now = DateTime.now();
  bool _adaptiveLayout = true;
  bool _showSeconds = false;
  bool _criticalWake = false;
  MissionControlProfile _profile = MissionControlProfile.balanced;

  @override
  void initState() {
    super.initState();
    _dashboardFuture = _fetchDashboard();
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
    _wakeTimer?.cancel();
    SirisScheduler.instance.unregister(_refreshJobId);
    super.dispose();
  }

  void _onEvent(SirisEvent event) {
    _diagnostics.recordEvent(event);
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

  Future<DashboardSummary> _fetchDashboard() async {
    final stopwatch = Stopwatch()..start();
    final result = await _dashboardService.fetchDashboard();
    stopwatch.stop();
    _diagnostics.recordRefresh(stopwatch.elapsed);
    _evaluateCriticalWake(result);
    return result;
  }

  void _evaluateCriticalWake(DashboardSummary dashboard) {
    final statuses = <String>[
      dashboard.homelab.status,
      dashboard.system.status,
      dashboard.running.status,
      dashboard.gym.status,
    ].map((status) => status.toLowerCase());
    final critical = statuses.any(
      (status) => status == 'critical' || status == 'error',
    );
    if (!critical || !mounted) return;
    _wakeTimer?.cancel();
    setState(() => _criticalWake = true);
    _wakeTimer = Timer(const Duration(seconds: 30), () {
      if (mounted) setState(() => _criticalWake = false);
    });
  }

  Future<void> _loadLayout() async {
    final layout = await _layoutService.load();
    if (mounted) setState(() => _layout = layout);
  }

  Future<void> _loadDisplayPreferences() async {
    final preferences = await SharedPreferences.getInstance();
    final savedProfile = preferences.getString(_profileKey);
    if (!mounted) return;
    setState(() {
      _adaptiveLayout = preferences.getBool(_adaptiveKey) ?? true;
      _showSeconds = preferences.getBool(_secondsKey) ?? false;
      _profile = MissionControlProfile.values.firstWhere(
        (profile) => profile.name == savedProfile,
        orElse: () => MissionControlProfile.balanced,
      );
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

  Future<void> _setProfile(MissionControlProfile profile) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_profileKey, profile.name);
    if (mounted) setState(() => _profile = profile);
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    final next = _fetchDashboard();
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
        child: StatefulBuilder(
          builder: (context, setSheetState) => Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Mission Control display',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<MissionControlProfile>(
                  value: _profile,
                  decoration: const InputDecoration(
                    labelText: 'Display profile',
                  ),
                  items: MissionControlProfile.values
                      .map(
                        (profile) => DropdownMenuItem<MissionControlProfile>(
                          value: profile,
                          child: Text(_profileLabel(profile)),
                        ),
                      )
                      .toList(growable: false),
                  onChanged: (profile) async {
                    if (profile == null) return;
                    await _setProfile(profile);
                    setSheetState(() {});
                  },
                ),
                const SizedBox(height: 8),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _adaptiveLayout,
                  title: const Text('Adaptive prioritisation'),
                  subtitle: const Text(
                    'Promote widgets that require attention without changing the saved layout.',
                  ),
                  onChanged: (value) async {
                    await _setAdaptiveLayout(value);
                    setSheetState(() {});
                  },
                ),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _showSeconds,
                  title: const Text('Show clock seconds'),
                  onChanged: (value) async {
                    await _setShowSeconds(value);
                    setSheetState(() {});
                  },
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.monitor_heart_rounded),
                  title: const Text('Runtime diagnostics'),
                  subtitle: Text(_diagnosticsSummary()),
                ),
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
      ),
    );
  }

  String _diagnosticsSummary() {
    final latency = _diagnostics.lastRefreshDuration?.inMilliseconds;
    final event = _diagnostics.lastEvent ?? 'None';
    return '${_diagnostics.eventCount} events · last $event · ${latency == null ? 'no refresh yet' : '${latency}ms refresh'}';
  }

  String get _time {
    final base = '${_two(_now.hour)}:${_two(_now.minute)}';
    return _showSeconds ? '$base:${_two(_now.second)}' : base;
  }

  String get _date {
    const weekdays = [
      'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
    ];
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December',
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
            final arranged = _priorityEngine.arrange(
              _layout,
              data,
              adaptive: _adaptiveLayout || _criticalWake,
            );
            final visible = _profile == MissionControlProfile.compact
                ? arranged.take(4).toList(growable: false)
                : arranged;

            return LayoutBuilder(
              builder: (context, constraints) {
                final columns = _columnsFor(constraints.maxWidth, _profile);
                final horizontalPadding =
                    _profile == MissionControlProfile.operations ? 18.0 : 24.0;
                final contentWidth = constraints.maxWidth - horizontalPadding * 2;
                const gap = 16.0;
                final unitWidth =
                    (contentWidth - gap * (columns - 1)) / columns;

                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: EdgeInsets.fromLTRB(
                      horizontalPadding,
                      18,
                      horizontalPadding,
                      32,
                    ),
                    children: [
                      _SituationHeader(
                        time: _time,
                        date: _date,
                        adaptive: _adaptiveLayout,
                        criticalWake: _criticalWake,
                        profile: _profile,
                        diagnostics: _diagnosticsSummary(),
                        onControls: _showDisplayControls,
                        onExit: () => Navigator.of(context).maybePop(),
                        onRefresh: _refresh,
                      ),
                      const SizedBox(height: 20),
                      Wrap(
                        spacing: gap,
                        runSpacing: gap,
                        children: visible.map<Widget>((item) {
                          final width = _widthFor(
                            item.size,
                            columns,
                            unitWidth,
                            gap,
                            contentWidth,
                          );
                          return AnimatedContainer(
                            key: ValueKey<String>(item.id),
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

  static int _columnsFor(double width, MissionControlProfile profile) {
    if (width < 700) return 1;
    if (profile == MissionControlProfile.compact) return width >= 1200 ? 4 : 2;
    if (profile == MissionControlProfile.operations) {
      return width >= 1500 ? 5 : width >= 1000 ? 4 : 2;
    }
    return width >= 1400 ? 4 : width >= 1000 ? 3 : 2;
  }

  static double _widthFor(
    MissionControlWidgetSize size,
    int columns,
    double unitWidth,
    double gap,
    double contentWidth,
  ) {
    if (columns == 1) return contentWidth;
    final span = size == MissionControlWidgetSize.wide ? columns : 1;
    return span >= columns
        ? contentWidth
        : unitWidth * span + gap * (span - 1);
  }

  static String _profileLabel(MissionControlProfile profile) => switch (profile) {
        MissionControlProfile.balanced => 'Balanced',
        MissionControlProfile.operations => 'Operations',
        MissionControlProfile.compact => 'Compact',
      };
}

class _SituationHeader extends StatelessWidget {
  const _SituationHeader({
    required this.time,
    required this.date,
    required this.adaptive,
    required this.criticalWake,
    required this.profile,
    required this.diagnostics,
    required this.onControls,
    required this.onExit,
    required this.onRefresh,
  });

  final String time;
  final String date;
  final bool adaptive;
  final bool criticalWake;
  final MissionControlProfile profile;
  final String diagnostics;
  final VoidCallback onControls;
  final VoidCallback onExit;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final wakeColor = Theme.of(context).colorScheme.error;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: criticalWake ? const EdgeInsets.all(16) : EdgeInsets.zero,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: criticalWake ? Border.all(color: wakeColor) : null,
        color: criticalWake ? wakeColor.withValues(alpha: 0.08) : null,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 10,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      'SIRIS MISSION CONTROL',
                      style: textTheme.labelLarge?.copyWith(
                        letterSpacing: 2.4,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Chip(
                      label: Text(_MissionControlScreenState._profileLabel(profile).toUpperCase()),
                      visualDensity: VisualDensity.compact,
                    ),
                    if (adaptive)
                      const Chip(
                        avatar: Icon(Icons.auto_awesome_rounded, size: 16),
                        label: Text('ADAPTIVE'),
                        visualDensity: VisualDensity.compact,
                      ),
                    if (criticalWake)
                      Chip(
                        avatar: Icon(Icons.warning_amber_rounded, size: 16, color: wakeColor),
                        label: const Text('CRITICAL WAKE'),
                        visualDensity: VisualDensity.compact,
                      ),
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
                const SizedBox(height: 6),
                Text(
                  diagnostics,
                  style: textTheme.labelSmall?.copyWith(
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
      ),
    );
  }
}
