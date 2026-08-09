import 'package:flutter/material.dart';

import '../core/engineering_calculators.dart';
import '../services/engineering_calculations_service.dart';
import '../services/engineering_standards_service.dart';
import '../widgets/standard_picker_dialog.dart';

enum _CalculatorId {
  fullPipe,
  partFullPipe,
  minimumGrade,
  rectangularChannel,
  trapezoidalChannel,
  criticalDepth,
  rationalMethod,
  weir,
  orifice,
  hazenWilliams,
  darcyWeisbach,
  pumpPower,
  buoyancy,
  detention,
}

class _CalculatorInfo {
  const _CalculatorInfo(this.title, this.category, this.note, this.icon);
  final String title;
  final String category;
  final String note;
  final IconData icon;
}

const _calculatorInfo = <_CalculatorId, _CalculatorInfo>{
  _CalculatorId.fullPipe: _CalculatorInfo('Full pipe Manning', 'Stormwater & pipes', 'Steady, uniform, full circular pipe flow using Manning’s equation.', Icons.circle_outlined),
  _CalculatorId.partFullPipe: _CalculatorInfo('Part-full pipe Manning', 'Stormwater & pipes', 'Circular-pipe flow at a specified water depth. Useful for gravity pipe checks below full depth.', Icons.water_rounded),
  _CalculatorId.minimumGrade: _CalculatorInfo('Minimum pipe grade', 'Stormwater & pipes', 'Solves Manning’s equation for the grade required to carry a target full-pipe flow.', Icons.trending_down_rounded),
  _CalculatorId.rectangularChannel: _CalculatorInfo('Rectangular channel', 'Open channels', 'Manning capacity for a rectangular open channel under steady uniform flow.', Icons.view_stream_rounded),
  _CalculatorId.trapezoidalChannel: _CalculatorInfo('Trapezoidal channel', 'Open channels', 'Manning capacity for a trapezoidal channel using horizontal:vertical side slopes.', Icons.filter_alt_outlined),
  _CalculatorId.criticalDepth: _CalculatorInfo('Rectangular critical depth', 'Open channels', 'Critical depth and velocity for a rectangular channel at a specified discharge.', Icons.height_rounded),
  _CalculatorId.rationalMethod: _CalculatorInfo('Rational Method', 'Hydrology', 'Peak flow using Q = C i A, with rainfall intensity in mm/h and area in hectares.', Icons.cloud_rounded),
  _CalculatorId.weir: _CalculatorInfo('Rectangular weir', 'Structures & controls', 'Free-flow rectangular sharp-crested weir equation using an entered discharge coefficient.', Icons.horizontal_rule_rounded),
  _CalculatorId.orifice: _CalculatorInfo('Circular orifice', 'Structures & controls', 'Free discharge through a circular orifice under a specified head.', Icons.blur_circular_rounded),
  _CalculatorId.hazenWilliams: _CalculatorInfo('Hazen–Williams headloss', 'Pressure pipes', 'SI Hazen–Williams friction headloss. Use an appropriate C value for the pipe material and condition.', Icons.waterfall_chart_rounded),
  _CalculatorId.darcyWeisbach: _CalculatorInfo('Darcy–Weisbach headloss', 'Pressure pipes', 'Pipe friction using Reynolds number and Swamee–Jain for turbulent flow; water viscosity defaults near 20 °C.', Icons.show_chart_rounded),
  _CalculatorId.pumpPower: _CalculatorInfo('Pump power', 'Pressure pipes', 'Hydraulic and estimated input power from flow, total dynamic head and pump efficiency.', Icons.bolt_rounded),
  _CalculatorId.buoyancy: _CalculatorInfo('Buried pipe buoyancy', 'Pipe design checks', 'Screening check for full submergence. Excludes side shear, anchors, slabs and project-specific load factors.', Icons.vertical_align_top_rounded),
  _CalculatorId.detention: _CalculatorInfo('Detention storage', 'Hydrology', 'Screening storage from constant inflow minus allowable outflow over a selected duration.', Icons.inventory_2_outlined),
};

class EngineeringScreen extends StatefulWidget {
  const EngineeringScreen({super.key});

  @override
  State<EngineeringScreen> createState() => _EngineeringScreenState();
}

class _EngineeringScreenState extends State<EngineeringScreen> {
  _CalculatorId _selected = _CalculatorId.fullPipe;
  final Map<String, TextEditingController> _controllers = {};
  final Map<String, String> _currentFieldLabels = {};
  List<_EngineeringResult>? _results;
  String? _error;
  final _calculationsService = EngineeringCalculationsService();
  bool _saving = false;

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  TextEditingController _controller(String key, String initial) =>
      _controllers.putIfAbsent(key, () => TextEditingController(text: initial));

  double _value(String key) => double.parse(_controllers[key]!.text.trim());

  Widget _field(String key, String label, String unit, String initial) {
    _currentFieldLabels[key] = unit.isEmpty ? label : '$label ($unit)';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: _controller(key, initial),
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        decoration: InputDecoration(
          labelText: label,
          suffixText: unit.isEmpty ? null : unit,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }

  List<Widget> _fields() {
    _currentFieldLabels.clear();
    return switch (_selected) {
        _CalculatorId.fullPipe => [
            _field('fp_d', 'Internal diameter', 'm', '0.45'),
            _field('fp_n', 'Manning n', '', '0.013'),
            _field('fp_s', 'Hydraulic grade', 'm/m', '0.005'),
          ],
        _CalculatorId.partFullPipe => [
            _field('pf_d', 'Internal diameter', 'm', '0.60'),
            _field('pf_y', 'Flow depth', 'm', '0.30'),
            _field('pf_n', 'Manning n', '', '0.013'),
            _field('pf_s', 'Hydraulic grade', 'm/m', '0.005'),
          ],
        _CalculatorId.minimumGrade => [
            _field('mg_d', 'Internal diameter', 'm', '0.45'),
            _field('mg_n', 'Manning n', '', '0.013'),
            _field('mg_q', 'Target flow', 'm³/s', '0.20'),
          ],
        _CalculatorId.rectangularChannel => [
            _field('rc_b', 'Channel width', 'm', '1.0'),
            _field('rc_y', 'Flow depth', 'm', '0.30'),
            _field('rc_n', 'Manning n', '', '0.015'),
            _field('rc_s', 'Channel grade', 'm/m', '0.005'),
          ],
        _CalculatorId.trapezoidalChannel => [
            _field('tc_b', 'Bottom width', 'm', '1.0'),
            _field('tc_y', 'Flow depth', 'm', '0.50'),
            _field('tc_z', 'Side slope H:V', '', '2.0'),
            _field('tc_n', 'Manning n', '', '0.030'),
            _field('tc_s', 'Channel grade', 'm/m', '0.005'),
          ],
        _CalculatorId.criticalDepth => [
            _field('cd_q', 'Flow', 'm³/s', '0.50'),
            _field('cd_b', 'Channel width', 'm', '1.0'),
          ],
        _CalculatorId.rationalMethod => [
            _field('rm_c', 'Runoff coefficient C', '0–1', '0.8'),
            _field('rm_i', 'Rainfall intensity', 'mm/h', '100'),
            _field('rm_a', 'Catchment area', 'ha', '1.0'),
          ],
        _CalculatorId.weir => [
            _field('wr_cd', 'Discharge coefficient Cd', '', '0.62'),
            _field('wr_b', 'Weir width', 'm', '1.0'),
            _field('wr_h', 'Head above crest', 'm', '0.30'),
          ],
        _CalculatorId.orifice => [
            _field('or_cd', 'Discharge coefficient Cd', '', '0.62'),
            _field('or_d', 'Orifice diameter', 'm', '0.15'),
            _field('or_h', 'Head to orifice centre', 'm', '1.0'),
          ],
        _CalculatorId.hazenWilliams => [
            _field('hw_q', 'Flow', 'm³/s', '0.05'),
            _field('hw_d', 'Internal diameter', 'm', '0.20'),
            _field('hw_l', 'Pipe length', 'm', '100'),
            _field('hw_c', 'Hazen–Williams C', '', '140'),
          ],
        _CalculatorId.darcyWeisbach => [
            _field('dw_q', 'Flow', 'm³/s', '0.05'),
            _field('dw_d', 'Internal diameter', 'm', '0.20'),
            _field('dw_l', 'Pipe length', 'm', '100'),
            _field('dw_e', 'Absolute roughness', 'mm', '0.045'),
          ],
        _CalculatorId.pumpPower => [
            _field('pp_q', 'Flow', 'm³/s', '0.05'),
            _field('pp_h', 'Total dynamic head', 'm', '20'),
            _field('pp_e', 'Pump efficiency', '%', '75'),
          ],
        _CalculatorId.buoyancy => [
            _field('bu_od', 'Outside diameter', 'm', '0.55'),
            _field('bu_id', 'Inside diameter', 'm', '0.45'),
            _field('bu_l', 'Pipe length checked', 'm', '1.0'),
            _field('bu_pd', 'Pipe material density', 'kg/m³', '2400'),
            _field('bu_c', 'Soil cover above crown', 'm', '0.75'),
            _field('bu_g', 'Submerged soil unit weight', 'kN/m³', '10'),
          ],
        _CalculatorId.detention => [
            _field('dt_qi', 'Peak inflow', 'm³/s', '0.20'),
            _field('dt_qo', 'Allowable outflow', 'm³/s', '0.10'),
            _field('dt_t', 'Critical duration', 'min', '30'),
          ],
      };
  }

  List<_EngineeringResult> _calculateValues() {
    switch (_selected) {
      case _CalculatorId.fullPipe:
        final r = EngineeringCalculators.fullCircularPipe(
          diameterM: _value('fp_d'), roughnessN: _value('fp_n'), slope: _value('fp_s'));
        return _flowResults(r.flowM3s, r.velocityMs);
      case _CalculatorId.partFullPipe:
        final r = EngineeringCalculators.partFullCircularPipe(
          diameterM: _value('pf_d'), depthM: _value('pf_y'), roughnessN: _value('pf_n'), slope: _value('pf_s'));
        return [..._flowResults(r.flowM3s, r.velocityMs), _EngineeringResult('Flow area', '${r.areaM2.toStringAsFixed(3)} m²')];
      case _CalculatorId.minimumGrade:
        final r = EngineeringCalculators.minimumCircularPipeGrade(
          diameterM: _value('mg_d'), roughnessN: _value('mg_n'), targetFlowM3s: _value('mg_q'));
        return [
          _EngineeringResult('Required slope', r.slope.toStringAsFixed(5)),
          _EngineeringResult('Required grade', '${r.gradePercent.toStringAsFixed(3)}%'),
          _EngineeringResult('Equivalent', '1 in ${(1 / r.slope).toStringAsFixed(0)}'),
        ];
      case _CalculatorId.rectangularChannel:
        final r = EngineeringCalculators.rectangularChannel(
          widthM: _value('rc_b'), depthM: _value('rc_y'), roughnessN: _value('rc_n'), slope: _value('rc_s'));
        return _flowResults(r.flowM3s, r.velocityMs);
      case _CalculatorId.trapezoidalChannel:
        final r = EngineeringCalculators.trapezoidalChannel(
          bottomWidthM: _value('tc_b'), depthM: _value('tc_y'), sideSlopeHorizontalToVertical: _value('tc_z'), roughnessN: _value('tc_n'), slope: _value('tc_s'));
        return [..._flowResults(r.flowM3s, r.velocityMs), _EngineeringResult('Flow area', '${r.areaM2.toStringAsFixed(3)} m²')];
      case _CalculatorId.criticalDepth:
        final r = EngineeringCalculators.rectangularCriticalDepth(flowM3s: _value('cd_q'), widthM: _value('cd_b'));
        return [_EngineeringResult('Critical depth', '${r.depthM.toStringAsFixed(3)} m'), _EngineeringResult('Critical velocity', '${r.velocityMs.toStringAsFixed(2)} m/s')];
      case _CalculatorId.rationalMethod:
        final r = EngineeringCalculators.rationalMethod(runoffCoefficient: _value('rm_c'), intensityMmHr: _value('rm_i'), areaHa: _value('rm_a'));
        return [_EngineeringResult('Peak flow', '${r.flowM3s.toStringAsFixed(3)} m³/s'), _EngineeringResult('Peak flow', '${r.flowLs.toStringAsFixed(0)} L/s')];
      case _CalculatorId.weir:
        final r = EngineeringCalculators.rectangularWeir(dischargeCoefficient: _value('wr_cd'), widthM: _value('wr_b'), headM: _value('wr_h'));
        return _dischargeResults(r);
      case _CalculatorId.orifice:
        final r = EngineeringCalculators.circularOrifice(dischargeCoefficient: _value('or_cd'), diameterM: _value('or_d'), headM: _value('or_h'));
        return [..._dischargeResults(r), if (r.velocityMs != null) _EngineeringResult('Jet velocity', '${r.velocityMs!.toStringAsFixed(2)} m/s')];
      case _CalculatorId.hazenWilliams:
        final r = EngineeringCalculators.hazenWilliams(flowM3s: _value('hw_q'), diameterM: _value('hw_d'), lengthM: _value('hw_l'), coefficientC: _value('hw_c'));
        return [_EngineeringResult('Friction headloss', '${r.headlossM.toStringAsFixed(2)} m'), _EngineeringResult('Velocity', '${r.velocityMs.toStringAsFixed(2)} m/s')];
      case _CalculatorId.darcyWeisbach:
        final r = EngineeringCalculators.darcyWeisbach(flowM3s: _value('dw_q'), diameterM: _value('dw_d'), lengthM: _value('dw_l'), absoluteRoughnessMm: _value('dw_e'));
        return [
          _EngineeringResult('Friction headloss', '${r.headlossM.toStringAsFixed(2)} m'),
          _EngineeringResult('Velocity', '${r.velocityMs.toStringAsFixed(2)} m/s'),
          _EngineeringResult('Reynolds number', r.reynoldsNumber!.toStringAsFixed(0)),
          _EngineeringResult('Darcy friction factor', r.frictionFactor!.toStringAsFixed(4)),
        ];
      case _CalculatorId.pumpPower:
        final r = EngineeringCalculators.pumpPower(flowM3s: _value('pp_q'), totalHeadM: _value('pp_h'), efficiencyPercent: _value('pp_e'));
        return [_EngineeringResult('Hydraulic power', '${r.hydraulicPowerKw.toStringAsFixed(2)} kW'), _EngineeringResult('Estimated input power', '${r.inputPowerKw.toStringAsFixed(2)} kW')];
      case _CalculatorId.buoyancy:
        final r = EngineeringCalculators.pipeBuoyancy(
          outsideDiameterM: _value('bu_od'), insideDiameterM: _value('bu_id'), lengthM: _value('bu_l'), pipeDensityKgM3: _value('bu_pd'), soilCoverM: _value('bu_c'), submergedSoilUnitWeightKnM3: _value('bu_g'));
        return [
          _EngineeringResult('Buoyant force', '${r.buoyantForceKn.toStringAsFixed(1)} kN'),
          _EngineeringResult('Resisting force', '${r.resistingForceKn.toStringAsFixed(1)} kN'),
          _EngineeringResult('Factor of safety', r.factorOfSafety.toStringAsFixed(2)),
          _EngineeringResult('Screening result', r.stable ? 'Resisting > uplift' : 'Uplift exceeds resistance'),
        ];
      case _CalculatorId.detention:
        final r = EngineeringCalculators.constantFlowDetention(inflowM3s: _value('dt_qi'), allowableOutflowM3s: _value('dt_qo'), durationMinutes: _value('dt_t'));
        return [_EngineeringResult('Required storage', '${r.storageM3.toStringAsFixed(1)} m³'), _EngineeringResult('Excess flow', '${((r.inflowM3s - r.outflowM3s).clamp(0, double.infinity) * 1000).toStringAsFixed(0)} L/s')];
    }
  }

  List<_EngineeringResult> _flowResults(double flow, double velocity) => [
        _EngineeringResult('Flow', '${flow.toStringAsFixed(3)} m³/s'),
        _EngineeringResult('Flow', '${(flow * 1000).toStringAsFixed(0)} L/s'),
        _EngineeringResult('Velocity', '${velocity.toStringAsFixed(2)} m/s'),
      ];

  List<_EngineeringResult> _dischargeResults(DischargeResult r) => [
        _EngineeringResult('Discharge', '${r.flowM3s.toStringAsFixed(3)} m³/s'),
        _EngineeringResult('Discharge', '${r.flowLs.toStringAsFixed(0)} L/s'),
      ];

  void _calculate() {
    setState(() {
      try {
        _results = _calculateValues();
        _error = null;
      } catch (_) {
        _results = null;
        _error = 'Check the entered values, geometry and units.';
      }
    });
  }

  Future<void> _saveCalculation() async {
    if (_saving || _results == null) return;
    final info = _calculatorInfo[_selected]!;
    final saveResult = await showDialog<_SaveCalculationResult>(
      context: context,
      builder: (context) => _SaveCalculationDialog(defaultTitle: info.title),
    );
    if (saveResult == null || saveResult.title.trim().isEmpty || !mounted) return;

    setState(() => _saving = true);
    try {
      final inputs = <String, double>{
        for (final entry in _currentFieldLabels.entries) entry.value: _value(entry.key),
      };
      final results = [
        for (final result in _results!) CalculationResultItem(label: result.label, value: result.value),
      ];
      await _calculationsService.save(
        calculatorId: _selected.name,
        title: saveResult.title.trim(),
        inputs: inputs,
        results: results,
        citedStandardId: saveResult.citedStandard?.id,
      );
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Calculation saved. Attach it to a project from Projects → Graph.')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to save calculation: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final info = _calculatorInfo[_selected]!;
    final grouped = <String, List<_CalculatorId>>{};
    for (final id in _CalculatorId.values) {
      grouped.putIfAbsent(_calculatorInfo[id]!.category, () => []).add(id);
    }

    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Row(
            children: [
              const Icon(Icons.engineering_rounded, size: 34),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Civil & Water Calculators', style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 2),
                    Text('Deterministic design checks with explicit assumptions and SI units.', style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          DropdownButtonFormField<_CalculatorId>(
            value: _selected,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Calculator', border: OutlineInputBorder()),
            items: [
              for (final entry in grouped.entries) ...[
                for (final id in entry.value)
                  DropdownMenuItem(value: id, child: Text('${entry.key} · ${_calculatorInfo[id]!.title}', overflow: TextOverflow.ellipsis)),
              ],
            ],
            onChanged: (value) {
              if (value == null) return;
              setState(() {
                _selected = value;
                _results = null;
                _error = null;
              });
            },
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: grouped.keys.map((category) {
              final selectedCategory = info.category == category;
              return FilterChip(
                selected: selectedCategory,
                label: Text(category),
                onSelected: (_) {
                  setState(() {
                    _selected = grouped[category]!.first;
                    _results = null;
                    _error = null;
                  });
                },
              );
            }).toList(growable: false),
          ),
          const SizedBox(height: 20),
          Align(
            alignment: Alignment.topLeft,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 760),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(info.icon),
                          const SizedBox(width: 10),
                          Expanded(child: Text(info.title, style: Theme.of(context).textTheme.titleLarge)),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(info.note, style: Theme.of(context).textTheme.bodySmall),
                      const SizedBox(height: 20),
                      ..._fields(),
                      FilledButton.icon(onPressed: _calculate, icon: const Icon(Icons.calculate_rounded), label: const Text('Calculate')),
                      if (_error != null) ...[
                        const SizedBox(height: 16),
                        Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                      ],
                      if (_results != null) ...[
                        const Divider(height: 32),
                        for (final result in _results!)
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: 5),
                            child: Row(
                              children: [
                                Expanded(child: Text(result.label)),
                                const SizedBox(width: 12),
                                Flexible(child: Text(result.value, textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w700))),
                              ],
                            ),
                          ),
                        const SizedBox(height: 12),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: OutlinedButton.icon(
                            onPressed: _saving ? null : _saveCalculation,
                            icon: _saving
                                ? const SizedBox.square(
                                    dimension: 16,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.save_outlined),
                            label: Text(_saving ? 'Saving…' : 'Save calculation'),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'These tools are calculation aids, not substitutes for project criteria, governing standards, manufacturer data or detailed hydraulic modelling.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _EngineeringResult {
  const _EngineeringResult(this.label, this.value);
  final String label;
  final String value;
}

class _SaveCalculationResult {
  const _SaveCalculationResult({required this.title, this.citedStandard});
  final String title;
  final EngineeringStandardDocument? citedStandard;
}

class _SaveCalculationDialog extends StatefulWidget {
  const _SaveCalculationDialog({required this.defaultTitle});
  final String defaultTitle;

  @override
  State<_SaveCalculationDialog> createState() => _SaveCalculationDialogState();
}

class _SaveCalculationDialogState extends State<_SaveCalculationDialog> {
  late final TextEditingController _title = TextEditingController(text: widget.defaultTitle);
  final _standardsService = EngineeringStandardsService();
  EngineeringStandardDocument? _citedStandard;

  @override
  void dispose() {
    _title.dispose();
    super.dispose();
  }

  Future<void> _pickStandard() async {
    final document = await showStandardPickerDialog(
      context,
      service: _standardsService,
      title: 'Cite a standard',
    );
    if (document != null && mounted) setState(() => _citedStandard = document);
  }

  void _submit() => Navigator.pop(
        context,
        _SaveCalculationResult(title: _title.text, citedStandard: _citedStandard),
      );

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Save calculation'),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _title,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Title', border: OutlineInputBorder()),
              onSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 16),
            Text('Cited standard (optional)', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 6),
            if (_citedStandard == null)
              OutlinedButton.icon(
                onPressed: _pickStandard,
                icon: const Icon(Icons.library_books_rounded),
                label: const Text('Cite a standard'),
              )
            else
              Chip(
                avatar: const Icon(Icons.library_books_rounded, size: 18),
                label: Text(standardIdentity(_citedStandard!)),
                onDeleted: () => setState(() => _citedStandard = null),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Save')),
      ],
    );
  }
}
