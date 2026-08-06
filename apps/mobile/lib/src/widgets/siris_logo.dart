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
  static const _assetPath = 'assets/branding/siris_logo_red.webp';

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
    final width = widget.showWordmark ? widget.size * 1.52 : widget.size;
    final height = widget.showWordmark ? width * (342 / 240) : widget.size;

    return RepaintBoundary(
      child: SizedBox(
        width: width,
        height: height,
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final progress = _controller.value;
            final breathingScale =
                1 + 0.012 * math.sin(progress * math.pi * 2);
            final brightness =
                0.96 + 0.04 * (0.5 + 0.5 * math.sin(progress * math.pi * 2));

            return Stack(
              clipBehavior: Clip.none,
              alignment: Alignment.center,
              children: [
                Positioned.fill(
                  child: CustomPaint(
                    painter: _LogoAtmospherePainter(
                      progress: progress,
                      showWordmark: widget.showWordmark,
                    ),
                  ),
                ),
                Transform.scale(
                  scale: breathingScale,
                  child: Opacity(
                    opacity: brightness,
                    child: widget.showWordmark
                        ? Image.asset(
                            _assetPath,
                            fit: BoxFit.contain,
                            filterQuality: FilterQuality.high,
                          )
                        : ClipRect(
                            child: SizedBox.square(
                              dimension: widget.size,
                              child: Align(
                                alignment: Alignment.topCenter,
                                child: SizedBox(
                                  width: widget.size * 0.98,
                                  height: widget.size * 1.397,
                                  child: Image.asset(
                                    _assetPath,
                                    fit: BoxFit.fill,
                                    filterQuality: FilterQuality.high,
                                  ),
                                ),
                              ),
                            ),
                          ),
                  ),
                ),
                Positioned.fill(
                  child: IgnorePointer(
                    child: CustomPaint(
                      painter: _LogoHighlightPainter(
                        progress: progress,
                        showWordmark: widget.showWordmark,
                      ),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _LogoAtmospherePainter extends CustomPainter {
  const _LogoAtmospherePainter({
    required this.progress,
    required this.showWordmark,
  });

  final double progress;
  final bool showWordmark;

  @override
  void paint(Canvas canvas, Size size) {
    final markHeight = showWordmark ? size.height * 0.69 : size.height;
    final centre = Offset(size.width * 0.5, markHeight * 0.45);
    final pulse = 0.75 + 0.25 * math.sin(progress * math.pi * 2);

    final glow = Paint()
      ..shader = RadialGradient(
        colors: [
          const Color(0xFFFF142B).withValues(alpha: 0.20 + 0.09 * pulse),
          const Color(0xFF79030B).withValues(alpha: 0.11),
          Colors.transparent,
        ],
        stops: const [0, 0.56, 1],
      ).createShader(
        Rect.fromCircle(center: centre, radius: size.width * 0.68),
      )
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * 0.08);
    canvas.drawOval(
      Rect.fromCenter(
        center: centre,
        width: size.width * 1.12,
        height: markHeight * 0.92,
      ),
      glow,
    );

    final particlePaint = Paint()..blendMode = BlendMode.screen;
    for (var index = 0; index < 18; index++) {
      final phase = progress * math.pi * 2 + index * 1.37;
      final clusterRight = index.isEven;
      final anchor = clusterRight
          ? Offset(size.width * 0.80, markHeight * 0.18)
          : Offset(size.width * 0.20, markHeight * 0.74);
      final radius = size.width * (0.045 + (index % 5) * 0.012);
      final point = Offset(
        anchor.dx + math.cos(phase * 1.15) * radius,
        anchor.dy + math.sin(phase * 0.86) * radius * 0.74,
      );
      final particlePulse =
          0.25 + 0.75 * (0.5 + 0.5 * math.sin(phase * 2.1));
      particlePaint
        ..color = const Color(0xFFFF2638).withValues(alpha: particlePulse)
        ..maskFilter = MaskFilter.blur(
          BlurStyle.normal,
          size.width * (0.004 + particlePulse * 0.006),
        );
      canvas.drawCircle(
        point,
        size.width * (0.004 + particlePulse * 0.004),
        particlePaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _LogoAtmospherePainter oldDelegate) =>
      oldDelegate.progress != progress ||
      oldDelegate.showWordmark != showWordmark;
}

class _LogoHighlightPainter extends CustomPainter {
  const _LogoHighlightPainter({
    required this.progress,
    required this.showWordmark,
  });

  final double progress;
  final bool showWordmark;

  Path _highlightPath(Size size) {
    final h = showWordmark ? size.height * 0.69 : size.height;
    return Path()
      ..moveTo(size.width * 0.78, h * 0.10)
      ..cubicTo(
        size.width * 0.58,
        h * 0.05,
        size.width * 0.25,
        h * 0.13,
        size.width * 0.16,
        h * 0.31,
      )
      ..cubicTo(
        size.width * 0.08,
        h * 0.47,
        size.width * 0.32,
        h * 0.54,
        size.width * 0.58,
        h * 0.59,
      )
      ..cubicTo(
        size.width * 0.82,
        h * 0.64,
        size.width * 0.78,
        h * 0.78,
        size.width * 0.56,
        h * 0.86,
      )
      ..cubicTo(
        size.width * 0.40,
        h * 0.92,
        size.width * 0.22,
        h * 0.88,
        size.width * 0.13,
        h * 0.82,
      );
  }

  @override
  void paint(Canvas canvas, Size size) {
    final path = _highlightPath(size);
    final metrics = path.computeMetrics().toList(growable: false);
    if (metrics.isEmpty) return;

    final metric = metrics.first;
    final segmentLength = metric.length * 0.13;
    final start = (progress * metric.length) % metric.length;
    final end = start + segmentLength;
    final segment = Path();

    if (end <= metric.length) {
      segment.addPath(metric.extractPath(start, end), Offset.zero);
    } else {
      segment.addPath(metric.extractPath(start, metric.length), Offset.zero);
      segment.addPath(metric.extractPath(0, end - metric.length), Offset.zero);
    }

    final glow = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = size.width * 0.055
      ..color = const Color(0xFFFFE8EA).withValues(alpha: 0.36)
      ..blendMode = BlendMode.screen
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * 0.032);
    canvas.drawPath(segment, glow);

    final shine = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = size.width * 0.010
      ..color = Colors.white.withValues(alpha: 0.86)
      ..blendMode = BlendMode.screen;
    canvas.drawPath(segment, shine);

    final tangent = metric.getTangentForOffset(start);
    if (tangent != null) {
      final flareGlow = Paint()
        ..color = const Color(0xFFFFEEF0).withValues(alpha: 0.72)
        ..blendMode = BlendMode.screen
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * 0.026);
      canvas.drawCircle(tangent.position, size.width * 0.018, flareGlow);

      final flareCore = Paint()
        ..color = Colors.white.withValues(alpha: 0.95)
        ..blendMode = BlendMode.screen;
      canvas.drawCircle(tangent.position, size.width * 0.0055, flareCore);
    }
  }

  @override
  bool shouldRepaint(covariant _LogoHighlightPainter oldDelegate) =>
      oldDelegate.progress != progress ||
      oldDelegate.showWordmark != showWordmark;
}
