import 'dart:math' as math;

import 'package:flutter/material.dart';

class SirisLogo extends StatefulWidget {
  const SirisLogo({this.size = 56, this.showWordmark = true, super.key});

  final double size;
  final bool showWordmark;

  @override
  State<SirisLogo> createState() => _SirisLogoState();
}

class _SirisLogoState extends State<SirisLogo>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 6),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mark = RepaintBoundary(
      child: SizedBox.square(
        dimension: widget.size,
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) => CustomPaint(
            painter: _SirisMarkPainter(progress: _controller.value),
          ),
        ),
      ),
    );

    if (!widget.showWordmark) return mark;

    final sirisSize = math.max(13.0, widget.size * 0.27);
    final osSize = math.max(10.0, widget.size * 0.18);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        SizedBox(height: widget.size * 0.10),
        ShaderMask(
          blendMode: BlendMode.srcIn,
          shaderCallback: (bounds) => const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFFFFFFFF),
              Color(0xFFE7E7E9),
              Color(0xFF8C8E94),
            ],
          ).createShader(bounds),
          child: Text(
            'SIRIS',
            style: TextStyle(
              color: Colors.white,
              fontSize: sirisSize,
              fontWeight: FontWeight.w800,
              letterSpacing: widget.size * 0.075,
              height: 0.95,
            ),
          ),
        ),
        SizedBox(height: widget.size * 0.085),
        SizedBox(
          width: widget.size * 1.18,
          child: Row(
            children: [
              const Expanded(child: _WordmarkLine()),
              SizedBox(width: widget.size * 0.10),
              Text(
                'OS',
                style: TextStyle(
                  color: const Color(0xFFFF2638),
                  fontSize: osSize,
                  fontWeight: FontWeight.w700,
                  letterSpacing: widget.size * 0.07,
                  height: 1,
                  shadows: const [
                    Shadow(color: Color(0xCCFF182D), blurRadius: 12),
                  ],
                ),
              ),
              SizedBox(width: widget.size * 0.10),
              const Expanded(child: _WordmarkLine()),
            ],
          ),
        ),
      ],
    );
  }
}

class _WordmarkLine extends StatelessWidget {
  const _WordmarkLine();

  @override
  Widget build(BuildContext context) => Container(
        height: 1,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.transparent, Color(0xFFFF2638)],
          ),
          boxShadow: [
            BoxShadow(color: Color(0xAAFF182D), blurRadius: 6),
          ],
        ),
      );
}

class _SirisMarkPainter extends CustomPainter {
  const _SirisMarkPainter({required this.progress});

  final double progress;

  Path _ribbonPath(double s) => Path()
    ..moveTo(s * 0.77, s * 0.14)
    ..cubicTo(
      s * 0.59,
      s * 0.08,
      s * 0.28,
      s * 0.15,
      s * 0.20,
      s * 0.33,
    )
    ..cubicTo(
      s * 0.14,
      s * 0.48,
      s * 0.34,
      s * 0.54,
      s * 0.55,
      s * 0.59,
    )
    ..cubicTo(
      s * 0.78,
      s * 0.65,
      s * 0.81,
      s * 0.79,
      s * 0.62,
      s * 0.89,
    )
    ..cubicTo(
      s * 0.48,
      s * 0.96,
      s * 0.28,
      s * 0.92,
      s * 0.16,
      s * 0.82,
    );

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.shortestSide;
    final rect = Offset.zero & size;
    final centre = size.center(Offset.zero);
    final ribbon = _ribbonPath(s);

    final halo = Paint()
      ..shader = RadialGradient(
        colors: [
          const Color(0xFFFF182D).withValues(alpha: 0.28),
          const Color(0xFF74040C).withValues(alpha: 0.10),
          Colors.transparent,
        ],
        stops: const [0, 0.52, 1],
      ).createShader(Rect.fromCircle(center: centre, radius: s * 0.58))
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, s * 0.10);
    canvas.drawOval(Rect.fromCenter(center: centre, width: s, height: s * 0.92), halo);

    final deepShadow = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = s * 0.205
      ..color = const Color(0xFF000000).withValues(alpha: 0.92)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, s * 0.035);
    canvas.drawPath(ribbon, deepShadow);

    final redGlow = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = s * 0.175
      ..color = const Color(0xFFFF1027).withValues(alpha: 0.40)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, s * 0.075);
    canvas.drawPath(ribbon, redGlow);

    final outerRibbon = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = s * 0.135
      ..shader = const LinearGradient(
        begin: Alignment.topRight,
        end: Alignment.bottomLeft,
        colors: [
          Color(0xFFFFA0A8),
          Color(0xFFFF2438),
          Color(0xFFB20817),
          Color(0xFF43030A),
          Color(0xFF120104),
        ],
        stops: [0, 0.20, 0.48, 0.76, 1],
      ).createShader(rect);
    canvas.drawPath(ribbon, outerRibbon);

    final darkCore = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = s * 0.070
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Color(0xFF4A4C52),
          Color(0xFF0B0B0E),
          Color(0xFF010102),
          Color(0xFF2C2D31),
        ],
      ).createShader(rect);
    canvas.drawPath(ribbon, darkCore);

    final silverEdge = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = s * 0.021
      ..shader = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Color(0xFFFFFFFF),
          Color(0xFFC5C7CC),
          Color(0xFF5C5F66),
          Color(0xFF121317),
        ],
      ).createShader(rect);
    canvas.drawPath(ribbon, silverEdge);

    final metrics = ribbon.computeMetrics().toList(growable: false);
    if (metrics.isNotEmpty) {
      final metric = metrics.first;
      final highlightLength = metric.length * 0.17;
      final start = (metric.length +
              progress * metric.length -
              highlightLength * 0.5) %
          metric.length;
      final end = start + highlightLength;
      final movingHighlight = Path();
      if (end <= metric.length) {
        movingHighlight.addPath(metric.extractPath(start, end), Offset.zero);
      } else {
        movingHighlight.addPath(
          metric.extractPath(start, metric.length),
          Offset.zero,
        );
        movingHighlight.addPath(
          metric.extractPath(0, end - metric.length),
          Offset.zero,
        );
      }

      final highlightGlow = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = s * 0.050
        ..color = const Color(0xFFFFF0F1).withValues(alpha: 0.46)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, s * 0.035);
      canvas.drawPath(movingHighlight, highlightGlow);

      final highlight = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = s * 0.016
        ..color = const Color(0xFFFFFFFF).withValues(alpha: 0.95);
      canvas.drawPath(movingHighlight, highlight);
    }

    final particlePaint = Paint();
    for (var index = 0; index < 10; index++) {
      final angle = progress * math.pi * 2 + index * 0.91;
      final radius = s * (0.34 + (index % 3) * 0.055);
      final pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(angle * 1.8));
      final particle = Offset(
        centre.dx + math.cos(angle) * radius,
        centre.dy + math.sin(angle * 1.15) * radius * 0.78,
      );
      particlePaint
        ..color = const Color(0xFFFF3348).withValues(alpha: pulse)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, s * 0.012);
      canvas.drawCircle(particle, s * (0.006 + pulse * 0.006), particlePaint);
    }

    final flareAngle = progress * math.pi * 2;
    final flare = Offset(
      centre.dx + math.cos(flareAngle) * s * 0.42,
      centre.dy + math.sin(flareAngle) * s * 0.33,
    );
    final flarePaint = Paint()
      ..color = const Color(0xFFFFE7E9).withValues(alpha: 0.85)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, s * 0.026);
    canvas.drawCircle(flare, s * 0.015, flarePaint);
  }

  @override
  bool shouldRepaint(covariant _SirisMarkPainter oldDelegate) =>
      oldDelegate.progress != progress;
}
