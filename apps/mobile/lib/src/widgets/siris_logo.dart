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
    final markWidth = widget.showWordmark ? widget.size * 2.05 : widget.size;
    final markHeight = markWidth * 1.04;

    final mark = RepaintBoundary(
      child: SizedBox(
        width: markWidth,
        height: markHeight,
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final progress = _controller.value;
            final breathingScale =
                1 + 0.012 * math.sin(progress * math.pi * 2);

            return Stack(
              clipBehavior: Clip.none,
              alignment: Alignment.center,
              children: [
                Positioned.fill(
                  child: CustomPaint(
                    painter: _LogoAtmospherePainter(progress: progress),
                  ),
                ),
                Transform.scale(
                  scale: breathingScale,
                  child: ClipRect(
                    child: Align(
                      alignment: Alignment.topCenter,
                      child: SizedBox(
                        width: markWidth,
                        height: markWidth * (667 / 468),
                        child: Image.asset(
                          _assetPath,
                          alignment: Alignment.topCenter,
                          fit: BoxFit.fill,
                          filterQuality: FilterQuality.high,
                          errorBuilder: (context, error, stackTrace) =>
                              _FallbackMark(size: markWidth),
                        ),
                      ),
                    ),
                  ),
                ),
                Positioned.fill(
                  child: IgnorePointer(
                    child: CustomPaint(
                      painter: _LogoHighlightPainter(progress: progress),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );

    if (!widget.showWordmark) return mark;

    return SizedBox(
      width: markWidth * 1.08,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          mark,
          SizedBox(height: widget.size * 0.10),
          _SirisWordmark(baseSize: widget.size),
          SizedBox(height: widget.size * 0.10),
          _OsWordmark(baseSize: widget.size),
        ],
      ),
    );
  }
}

class _SirisWordmark extends StatelessWidget {
  const _SirisWordmark({required this.baseSize});

  final double baseSize;

  @override
  Widget build(BuildContext context) {
    final fontSize = math.max(16.0, baseSize * 0.43);
    return ShaderMask(
      blendMode: BlendMode.srcIn,
      shaderCallback: (bounds) => const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Color(0xFFFFFFFF),
          Color(0xFFF2F2F3),
          Color(0xFF92949A),
          Color(0xFFF3F3F4),
        ],
        stops: [0, 0.28, 0.68, 1],
      ).createShader(bounds),
      child: Text(
        'SIRIS',
        maxLines: 1,
        style: TextStyle(
          color: Colors.white,
          fontSize: fontSize,
          fontWeight: FontWeight.w800,
          letterSpacing: baseSize * 0.14,
          height: 1,
          shadows: const [
            Shadow(color: Color(0xAAFF1D31), blurRadius: 5),
            Shadow(color: Color(0xFF000000), blurRadius: 10, offset: Offset(0, 3)),
          ],
        ),
      ),
    );
  }
}

class _OsWordmark extends StatelessWidget {
  const _OsWordmark({required this.baseSize});

  final double baseSize;

  @override
  Widget build(BuildContext context) {
    final fontSize = math.max(13.0, baseSize * 0.31);
    return Row(
      children: [
        const Expanded(child: _WordmarkLine(reverse: false)),
        SizedBox(width: baseSize * 0.14),
        Text(
          'OS',
          style: TextStyle(
            color: const Color(0xFFFF283A),
            fontSize: fontSize,
            fontWeight: FontWeight.w700,
            letterSpacing: baseSize * 0.12,
            height: 1,
            shadows: const [
              Shadow(color: Color(0xFFFF1027), blurRadius: 12),
              Shadow(color: Color(0xFF000000), blurRadius: 8, offset: Offset(0, 2)),
            ],
          ),
        ),
        SizedBox(width: baseSize * 0.14),
        const Expanded(child: _WordmarkLine(reverse: true)),
      ],
    );
  }
}

class _WordmarkLine extends StatelessWidget {
  const _WordmarkLine({required this.reverse});

  final bool reverse;

  @override
  Widget build(BuildContext context) {
    final colors = reverse
        ? const [Color(0xFFFF2638), Colors.transparent]
        : const [Colors.transparent, Color(0xFFFF2638)];
    return Container(
      height: 2,
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: colors),
        boxShadow: const [
          BoxShadow(color: Color(0xCCFF182D), blurRadius: 7),
        ],
      ),
    );
  }
}

class _FallbackMark extends StatelessWidget {
  const _FallbackMark({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) => Center(
        child: Text(
          'S',
          style: TextStyle(
            color: const Color(0xFFFF2638),
            fontSize: size * 0.72,
            fontWeight: FontWeight.w900,
            fontStyle: FontStyle.italic,
            height: 1,
            shadows: const [
              Shadow(color: Color(0xFFFF1027), blurRadius: 20),
            ],
          ),
        ),
      );
}

class _LogoAtmospherePainter extends CustomPainter {
  const _LogoAtmospherePainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final centre = Offset(size.width * 0.5, size.height * 0.48);
    final pulse = 0.5 + 0.5 * math.sin(progress * math.pi * 2);

    final glow = Paint()
      ..shader = RadialGradient(
        colors: [
          const Color(0xFFFF142B).withValues(alpha: 0.20 + 0.10 * pulse),
          const Color(0xFF79030B).withValues(alpha: 0.10),
          Colors.transparent,
        ],
        stops: const [0, 0.55, 1],
      ).createShader(
        Rect.fromCircle(center: centre, radius: size.width * 0.62),
      )
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * 0.08);
    canvas.drawOval(
      Rect.fromCenter(
        center: centre,
        width: size.width * 1.12,
        height: size.height * 0.94,
      ),
      glow,
    );

    final particlePaint = Paint()..blendMode = BlendMode.screen;
    for (var index = 0; index < 16; index++) {
      final phase = progress * math.pi * 2 + index * 1.37;
      final upperCluster = index.isEven;
      final anchor = upperCluster
          ? Offset(size.width * 0.80, size.height * 0.15)
          : Offset(size.width * 0.19, size.height * 0.82);
      final radius = size.width * (0.035 + (index % 5) * 0.012);
      final point = Offset(
        anchor.dx + math.cos(phase * 1.15) * radius,
        anchor.dy + math.sin(phase * 0.86) * radius * 0.72,
      );
      final particlePulse =
          0.25 + 0.75 * (0.5 + 0.5 * math.sin(phase * 2.1));
      particlePaint
        ..color = const Color(0xFFFF2638).withValues(alpha: particlePulse)
        ..maskFilter = MaskFilter.blur(
          BlurStyle.normal,
          size.width * (0.004 + particlePulse * 0.005),
        );
      canvas.drawCircle(
        point,
        size.width * (0.0035 + particlePulse * 0.004),
        particlePaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _LogoAtmospherePainter oldDelegate) =>
      oldDelegate.progress != progress;
}

class _LogoHighlightPainter extends CustomPainter {
  const _LogoHighlightPainter({required this.progress});

  final double progress;

  Path _highlightPath(Size size) => Path()
    ..moveTo(size.width * 0.79, size.height * 0.08)
    ..cubicTo(
      size.width * 0.58,
      size.height * 0.04,
      size.width * 0.26,
      size.height * 0.12,
      size.width * 0.16,
      size.height * 0.31,
    )
    ..cubicTo(
      size.width * 0.08,
      size.height * 0.47,
      size.width * 0.31,
      size.height * 0.55,
      size.width * 0.59,
      size.height * 0.60,
    )
    ..cubicTo(
      size.width * 0.82,
      size.height * 0.65,
      size.width * 0.78,
      size.height * 0.80,
      size.width * 0.55,
      size.height * 0.90,
    )
    ..cubicTo(
      size.width * 0.39,
      size.height * 0.97,
      size.width * 0.20,
      size.height * 0.91,
      size.width * 0.12,
      size.height * 0.83,
    );

  @override
  void paint(Canvas canvas, Size size) {
    final path = _highlightPath(size);
    final metrics = path.computeMetrics().toList(growable: false);
    if (metrics.isEmpty) return;

    final metric = metrics.first;
    final segmentLength = metric.length * 0.12;
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
      ..strokeWidth = size.width * 0.048
      ..color = const Color(0xFFFFE8EA).withValues(alpha: 0.34)
      ..blendMode = BlendMode.screen
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * 0.030);
    canvas.drawPath(segment, glow);

    final shine = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = size.width * 0.009
      ..color = Colors.white.withValues(alpha: 0.88)
      ..blendMode = BlendMode.screen;
    canvas.drawPath(segment, shine);

    final tangent = metric.getTangentForOffset(start);
    if (tangent != null) {
      final flareGlow = Paint()
        ..color = const Color(0xFFFFEEF0).withValues(alpha: 0.72)
        ..blendMode = BlendMode.screen
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.width * 0.025);
      canvas.drawCircle(tangent.position, size.width * 0.017, flareGlow);
    }
  }

  @override
  bool shouldRepaint(covariant _LogoHighlightPainter oldDelegate) =>
      oldDelegate.progress != progress;
}
