import 'dart:math' as math;

import 'package:flutter/material.dart';

class MetricSample {
  const MetricSample({required this.time, required this.value});

  final DateTime time;
  final double value;
}

class MetricLineChart extends StatelessWidget {
  const MetricLineChart({
    required this.title,
    required this.samples,
    required this.valueSuffix,
    this.maxY,
    super.key,
  });

  final String title;
  final List<MetricSample> samples;
  final String valueSuffix;
  final double? maxY;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final latest = samples.isEmpty ? null : samples.last.value;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Text(
                  latest == null ? '—' : '${latest.toStringAsFixed(1)}$valueSuffix',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: scheme.primary,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              samples.length < 2
                  ? 'Collecting live samples…'
                  : 'Rolling live history · ${samples.length} samples',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 18),
            SizedBox(
              height: 150,
              width: double.infinity,
              child: samples.length < 2
                  ? Center(
                      child: Icon(
                        Icons.show_chart_rounded,
                        size: 42,
                        color: scheme.onSurfaceVariant,
                      ),
                    )
                  : CustomPaint(
                      painter: _MetricChartPainter(
                        samples: samples,
                        lineColor: scheme.primary,
                        gridColor: scheme.outlineVariant.withValues(alpha: 0.45),
                        fillColor: scheme.primary.withValues(alpha: 0.12),
                        maxY: maxY,
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricChartPainter extends CustomPainter {
  const _MetricChartPainter({
    required this.samples,
    required this.lineColor,
    required this.gridColor,
    required this.fillColor,
    required this.maxY,
  });

  final List<MetricSample> samples;
  final Color lineColor;
  final Color gridColor;
  final Color fillColor;
  final double? maxY;

  @override
  void paint(Canvas canvas, Size size) {
    const leftPadding = 4.0;
    const topPadding = 6.0;
    const bottomPadding = 8.0;
    final chartWidth = size.width - leftPadding;
    final chartHeight = size.height - topPadding - bottomPadding;

    final gridPaint = Paint()
      ..color = gridColor
      ..strokeWidth = 1;

    for (var i = 0; i <= 3; i++) {
      final y = topPadding + chartHeight * i / 3;
      canvas.drawLine(
        Offset(leftPadding, y),
        Offset(size.width, y),
        gridPaint,
      );
    }

    final observedMax = samples.fold<double>(
      0,
      (current, sample) => math.max(current, sample.value),
    );
    final upperBound = math.max(maxY ?? 0, math.max(observedMax * 1.2, 1));

    final points = <Offset>[];
    for (var i = 0; i < samples.length; i++) {
      final x = leftPadding + chartWidth * i / (samples.length - 1);
      final normalised = (samples[i].value / upperBound).clamp(0.0, 1.0);
      final y = topPadding + chartHeight * (1 - normalised);
      points.add(Offset(x, y));
    }

    final linePath = Path()..moveTo(points.first.dx, points.first.dy);
    for (final point in points.skip(1)) {
      linePath.lineTo(point.dx, point.dy);
    }

    final fillPath = Path.from(linePath)
      ..lineTo(points.last.dx, topPadding + chartHeight)
      ..lineTo(points.first.dx, topPadding + chartHeight)
      ..close();

    canvas.drawPath(fillPath, Paint()..color = fillColor);
    canvas.drawPath(
      linePath,
      Paint()
        ..color = lineColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );

    canvas.drawCircle(points.last, 4, Paint()..color = lineColor);
  }

  @override
  bool shouldRepaint(covariant _MetricChartPainter oldDelegate) {
    return oldDelegate.samples != samples ||
        oldDelegate.lineColor != lineColor ||
        oldDelegate.gridColor != gridColor ||
        oldDelegate.fillColor != fillColor ||
        oldDelegate.maxY != maxY;
  }
}
