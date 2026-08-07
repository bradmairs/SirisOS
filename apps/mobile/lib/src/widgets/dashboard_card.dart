import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'siris_design_system.dart';

class DashboardCard extends StatelessWidget {
  const DashboardCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.subtitle,
    required this.status,
    this.trend = const [],
    super.key,
  });

  final String title;
  final String value;
  final IconData icon;
  final String subtitle;
  final String status;
  final List<double> trend;

  @override
  Widget build(BuildContext context) {
    final accent = switch (title.toLowerCase()) {
      'homelab' => AppTheme.success,
      'running' => AppTheme.info,
      'gym' => const Color(0xFFC98BFF),
      'server' => AppTheme.primaryBright,
      _ => Theme.of(context).colorScheme.primary,
    };
    final normalized = status.toLowerCase();
    final statusType = switch (normalized) {
      'critical' || 'error' => SirisStatus.critical,
      'warning' || 'unhealthy' => SirisStatus.warning,
      'healthy' || 'success' || 'ok' => SirisStatus.success,
      _ => SirisStatus.neutral,
    };
    final emphasised = statusType == SirisStatus.critical || statusType == SirisStatus.warning;

    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: 1),
      duration: const Duration(milliseconds: 420),
      curve: Curves.easeOutCubic,
      builder: (context, progress, child) => Opacity(
        opacity: progress,
        child: Transform.translate(
          offset: Offset(0, 8 * (1 - progress)),
          child: child,
        ),
      ),
      child: SirisCard(
        accent: emphasised ? _statusAccent(context, statusType) : accent,
        emphasised: emphasised,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(13),
                    border: Border.all(color: accent.withValues(alpha: 0.28)),
                  ),
                  child: Icon(icon, color: accent, size: 21),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                SirisStatusChip(
                  label: _statusLabel(status),
                  status: statusType,
                ),
              ],
            ),
            const Spacer(),
            if (trend.length >= 2) ...[
              SizedBox(
                height: 32,
                width: double.infinity,
                child: CustomPaint(
                  painter: _SparklinePainter(values: trend, color: accent),
                ),
              ),
              const SizedBox(height: 8),
            ],
            SirisMetric(
              label: title,
              value: value,
              detail: subtitle,
              accent: accent,
            ),
          ],
        ),
      ),
    );
  }

  static Color _statusAccent(BuildContext context, SirisStatus status) => switch (status) {
        SirisStatus.critical => Theme.of(context).colorScheme.error,
        SirisStatus.warning => AppTheme.warning,
        SirisStatus.success => AppTheme.success,
        SirisStatus.info => AppTheme.info,
        SirisStatus.neutral => Theme.of(context).colorScheme.onSurfaceVariant,
      };

  static String _statusLabel(String status) {
    final normalized = status.trim();
    if (normalized.isEmpty) return 'STATUS';
    return normalized.toUpperCase();
  }
}

class _SparklinePainter extends CustomPainter {
  const _SparklinePainter({required this.values, required this.color});

  final List<double> values;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2 || size.isEmpty) return;

    final minimum = values.reduce(math.min);
    final maximum = values.reduce(math.max);
    final range = maximum - minimum;
    final path = Path();

    for (var index = 0; index < values.length; index++) {
      final x = size.width * index / (values.length - 1);
      final normalised = range == 0 ? 0.5 : (values[index] - minimum) / range;
      final y = size.height - (normalised * (size.height - 4)) - 2;
      if (index == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    final fillPath = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();

    canvas.drawPath(
      fillPath,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            color.withValues(alpha: 0.18),
            color.withValues(alpha: 0),
          ],
        ).createShader(Offset.zero & size),
    );

    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter oldDelegate) =>
      oldDelegate.values != values || oldDelegate.color != color;
}
