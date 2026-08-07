import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/mission_control_diagnostics.dart';
import '../core/mission_control_focus.dart';
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
  static const _focusKey = 'mission.focus_mode';
  static const _ambientKey = 'mission.ambient_enabled';
  static const _reducedMotionKey = 'mission.reduced_motion';
  static const _ambientDelay = Duration(seconds: 30);

  final DashboardService _dashboardService = DashboardService();
  final DashboardLayoutService _layoutService = DashboardLayoutService();
  final MissionControlPriorityEngine _priorityEngine =
      const MissionControlPriorityEngine();
  final MissionControlFocusEngine _focusEngine = const MissionControlFocusEngine();
  final MissionControlDiagnostics _diagnostics = MissionControlDiagnostics();

  late Future<DashboardSummary> _dashboardFuture;
  List<DashboardWidgetPreference> _layout =
      DashboardLayoutService.defaultLayout();
  StreamSubscription<SirisEvent>? _events;
  Timer? _clockTimer;
  Timer? _refreshDebounce;
  Timer? _wakeTimer;
  Timer? _ambientTimer;
  DateTime _now = DateTime.now();
  bool _adaptiveLayout = true;
  bool _showSeconds = false;
  bool _criticalWake = false;
  bool _ambientEnabled = true;
  bool _ambientMode = false;
  bool _reducedMotion = false;
  MissionControlProfile _profile = MissionControlProfile.balanced;
  MissionControlFocus _focus = MissionControlFocus.all;

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
    _resetAmbientTimer();
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
    _ambientTimer?.cancel();
    SirisScheduler.instance.unregister(_refreshJobId);
    super.dispose();
  }

  void _onEvent(SirisEvent event) {
    _diagnostics.recordEvent(event);
    if (event is MissionControlRefreshed && event.source == 'dashboard_service') {
      return;
    }
    if (event is! ModuleDataChanged && event is! NotificationStateChanged) return;
    _wakeFromAmbient();
    _refreshDebounce?.cancel();
    _refreshDebounce = Timer(const Duration(milliseconds: 350), _refresh);
  }

  void _recordInteraction() {
    if (_ambientMode) setState(() => _ambientMode = false);
    _resetAmbientTimer();
  }

  void _wakeFromAmbient() {
    if (!mounted) return;
    if (_ambientMode) setState(() => _ambientMode = false);
    _resetAmbientTimer();
  }

  void _resetAmbientTimer() {
    _ambientTimer?.cancel();
    if (!_ambientEnabled) return;
    _ambientTimer = Timer(_ambientDelay, () {
      if (mounted && !_criticalWake) setState(() => _ambientMode = true);
    });
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
    _ambientTimer?.cancel();
    _wakeTimer?.cancel();
    setState(() {
      _criticalWake = true;
      _ambientMode = false;
    });
    _wakeTimer = Timer(const Duration(seconds: 30), () {
      if (!mounted) return;
      setState(() => _criticalWake = false);
      _resetAmbientTimer();
    });
  }

  Future<void> _loadLayout() async {
    final layout = await _layoutService.load();
    if (mounted) setState(() => _layout = layout);
  }

  Future<void> _loadDisplayPreferences() async {
    final preferences = await SharedPreferences.getInstance();
    final savedProfile = preferences.getString(_profileKey);
    final savedFocus = preferences.getString(_focusKey);
    if (!mounted) return;
    setState(() {
      _adaptiveLayout = preferences.getBool(_adaptiveKey) ?? true;
      _showSeconds = preferences.getBool(_secondsKey) ?? false;
      _ambientEnabled = preferences.getBool(_ambientKey) ?? true;
      _reducedMotion = preferences.getBool(_reducedMotionKey) ?? false;
      _profile = MissionControlProfile.values.firstWhere(
        (value) => value.name == savedProfile,
        orElse: () => MissionControlProfile.balanced,
      );
      _focus = MissionControlFocus.values.firstWhere(
        (value) => value.name == savedFocus,
        orElse: () => MissionControlFocus.all,
      );
    });
    _resetAmbientTimer();
  }

  Future<void> _setBool(String key, bool value, VoidCallback apply) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool(key, value);
    if (mounted) setState(apply);
  }

  Future<void> _setAdaptiveLayout(bool value) =>
      _setBool(_adaptiveKey, value, () => _adaptiveLayout = value);

  Future<void> _setShowSeconds(bool value) =>
      _setBool(_secondsKey, value, () => _showSeconds = value);

  Future<void> _setReducedMotion(bool value) =>
      _setBool(_reducedMotionKey, value, () => _reducedMotion = value);

  Future<void> _setAmbientEnabled(bool value) async {
    await _setBool(_ambientKey, value, () {
      _ambientEnabled = value;
      if (!value) _ambientMode = false;
    });
    _resetAmbientTimer();
  }

  Future<void> _setProfile(MissionControlProfile profile) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_profileKey, profile.name);
    if (mounted) setState(() => _profile = profile);
  }

  Future<void> _setFocus(MissionControlFocus focus) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_focusKey, focus.name);
    if (mounted) setState(() => _focus = focus);
    _recordInteraction();
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
    _recordInteraction();
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: StatefulBuilder(
          builder: (context, setSheetState) => SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Mission Control display', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 12),
                DropdownButtonFormField<MissionControlProfile>(
                  value: _profile,
                  decoration: const InputDecoration(labelText: 'Display profile'),
                  items: MissionControlProfile.values
                      .map((value) => DropdownMenuItem<MissionControlProfile>(
                            value: value,
                            child: Text(_profileLabel(value)),
                          ))
                      .toList(growable: false),
                  onChanged: (value) async {
                    if (value == null) return;
                    await _setProfile(value);
                    setSheetState(() {});
                  },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<MissionControlFocus>(
                  value: _focus,
                  decoration: const InputDecoration(labelText: 'Focus mode'),
                  items: MissionControlFocus.values
                      .map((value) => DropdownMenuItem<MissionControlFocus>(
                            value: value,
                            child: Text(_focusLabel(value)),
                          ))
                      .toList(growable: false),
                  onChanged: (value) async {
                    if (value == null) return;
                    await _setFocus(value);
                    setSheetState(() {});
                  },
                ),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _adaptiveLayout,
                  title: const Text('Adaptive prioritisation'),
                  subtitle: const Text('Promote widgets that require attention without changing the saved layout.'),
                  onChanged: (value) async {
                    await _setAdaptiveLayout(value);
                    setSheetState(() {});
                  },
                ),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _ambientEnabled,
                  title: const Text('Ambient mode'),
                  subtitle: const Text('Simplify the display after 30 seconds of inactivity.'),
                  onChanged: (value) async {
                    await _setAmbientEnabled(value);
                    setSheetState(() {});
                  },
                ),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _reducedMotion,
                  title: const Text('Reduced motion'),
                  subtitle: const Text('Disable non-essential Mission Control transitions.'),
                  onChanged: (value) async {
                    await _setReducedMotion(value);
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
    return _showSeconds && !_ambientMode ? '$base:${_two(_now.second)}' : base;
  }

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
    final duration = _reducedMotion ? Duration.zero : const Duration(milliseconds: 300);
    return Listener(
      behavior: HitTestBehavior.translucent,
      onPointerDown: (_) => _recordInteraction(),
      onPointerHover: (_) => _recordInteraction(),
      child: Scaffold(
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
              final arranged = _priorityEngine.arrange(
                _layout,
                data,
                adaptive: _adaptiveLayout || _criticalWake,
              );
              final focused = _focusEngine.apply(arranged, _focus);
              final profileWidgets = _profile == MissionControlProfile.compact
                  ? focused.take(4).toList(growable: false)
                  : focused;
              final visible = _ambientMode && !_criticalWake
                  ? profileWidgets.take(3).toList(growable: false)
                  : profileWidgets;

              return LayoutBuilder(
                builder: (context, constraints) {
                  final columns = _columnsFor(constraints.maxWidth, _profile, _ambientMode);
                  final horizontalPadding = _profile == MissionControlProfile.operations ? 18.0 : 24.0;
                  final contentWidth = constraints.maxWidth - horizontalPadding * 2;
                  const gap = 16.0;
                  final unitWidth = (contentWidth - gap * (columns - 1)) / columns;

                  return RefreshIndicator(
                    onRefresh: _refresh,
                    child: ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: EdgeInsets.fromLTRB(horizontalPadding, 18, horizontalPadding, 32),
                      children: [
                        _SituationHeader(
                          time: _time,
                          date: _date,
                          adaptive: _adaptiveLayout,
                          ambient: _ambientMode,
                          criticalWake: _criticalWake,
                          profile: _profile,
                          focus: _focus,
                          diagnostics: _diagnosticsSummary(),
                          duration: duration,
                          onControls: _showDisplayControls,
                          onExit: () => Navigator.of(context).maybePop(),
                          onRefresh: _refresh,
                        ),
                        SizedBox(height: _ambientMode ? 28 : 20),
                        Wrap(
                          spacing: gap,
                          runSpacing: gap,
                          children: visible.map<Widget>((item) {
                            final width = _ambientMode
                                ? contentWidth
                                : _widthFor(item.size, columns, unitWidth, gap, contentWidth);
                            return AnimatedContainer(
                              key: ValueKey<String>(item.id),
                              duration: duration,
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
      ),
    );
  }

  static int _columnsFor(
    double width,
    MissionControlProfile profile,
    bool ambient,
  ) {
    if (ambient || width < 700) return 1;
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
    return span >= columns ? contentWidth : unitWidth * span + gap * (span - 1);
  }

  static String _profileLabel(MissionControlProfile value) => switch (value) {
        MissionControlProfile.balanced => 'Balanced',
        MissionControlProfile.operations => 'Operations',
        MissionControlProfile.compact => 'Compact',
      };

  static String _focusLabel(MissionControlFocus value) => switch (value) {
        MissionControlFocus.all => 'All',
        MissionControlFocus.work => 'Work',
        MissionControlFocus.home => 'Home',
        MissionControlFocus.fitness => 'Fitness',
        MissionControlFocus.travel => 'Travel',
      };
}

class _SituationHeader extends StatelessWidget {
  const _SituationHeader({
    required this.time,
    required this.date,
    required this.adaptive,
    required this.ambient,
    required this.criticalWake,
    required this.profile,
    required this.focus,
    required this.diagnostics,
    required this.duration,
    required this.onControls,
    required this.onExit,
    required this.onRefresh,
  });

  final String time;
  final String date;
  final bool adaptive;
  final bool ambient;
  final bool criticalWake;
  final MissionControlProfile profile;
  final MissionControlFocus focus;
  final String diagnostics;
  final Duration duration;
  final VoidCallback onControls;
  final VoidCallback onExit;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final wakeColor = Theme.of(context).colorScheme.error;
    return AnimatedContainer(
      duration: duration,
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
                AnimatedOpacity(
                  duration: duration,
                  opacity: ambient ? 0.55 : 1,
                  child: Wrap(
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
                      if (focus != MissionControlFocus.all)
                        Chip(
                          label: Text(_MissionControlScreenState._focusLabel(focus).toUpperCase()),
                          visualDensity: VisualDensity.compact,
                        ),
                      if (adaptive)
                        const Chip(
                          avatar: Icon(Icons.auto_awesome_rounded, size: 16),
                          label: Text('ADAPTIVE'),
                          visualDensity: VisualDensity.compact,
                        ),
                      if (ambient)
                        const Chip(
                          avatar: Icon(Icons.nights_stay_rounded, size: 16),
                          label: Text('AMBIENT'),
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
                ),
                SizedBox(height: ambient ? 18 : 10),
                AnimatedDefaultTextStyle(
                  duration: duration,
                  style: (ambient
                          ? textTheme.displayLarge?.copyWith(fontSize: 88)
                          : textTheme.displayLarge)
                      ?.copyWith(fontWeight: FontWeight.w300, height: 0.95) ??
                      const TextStyle(fontSize: 64),
                  child: Text(time),
                ),
                const SizedBox(height: 8),
                Text(
                  date,
                  style: textTheme.titleMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                if (!ambient) ...[
                  const SizedBox(height: 6),
                  Text(
                    diagnostics,
                    style: textTheme.labelSmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
          AnimatedOpacity(
            duration: duration,
            opacity: ambient ? 0 : 1,
            child: IgnorePointer(
              ignoring: ambient,
              child: Row(
                children: [
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
            ),
          ),
        ],
      ),
    );
  }
}
