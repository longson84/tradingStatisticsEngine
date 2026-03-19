"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import type { StrategyConfig, MaType } from "@/lib/api";

interface Props {
  value: StrategyConfig;
  onChange: (v: StrategyConfig) => void;
}

export function StrategyPicker({ value, onChange }: Props) {
  const isCrossover = value.type === "ma_crossover";
  const cfg = isCrossover ? value : { type: "ma_crossover" as const };

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label>Strategy</Label>
        <Select
          value={value.type}
          onValueChange={(t) =>
            onChange(
              t === "buy_and_hold"
                ? { type: "buy_and_hold", weight: 1.0 }
                : { type: "ma_crossover", fast_period: 10, slow_period: 50, ma_type: "sma" }
            )
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="buy_and_hold">Buy &amp; Hold</SelectItem>
            <SelectItem value="ma_crossover">MA Crossover</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isCrossover && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label>Fast period</Label>
              <Input
                type="number"
                min={1}
                value={(value as any).fast_period ?? 10}
                onChange={(e) =>
                  onChange({ ...value, fast_period: Number(e.target.value) } as any)
                }
              />
            </div>
            <div className="space-y-1">
              <Label>Slow period</Label>
              <Input
                type="number"
                min={1}
                value={(value as any).slow_period ?? 50}
                onChange={(e) =>
                  onChange({ ...value, slow_period: Number(e.target.value) } as any)
                }
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label>MA type</Label>
            <Select
              value={(value as any).ma_type ?? "sma"}
              onValueChange={(t) => onChange({ ...value, ma_type: t as MaType } as any)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sma">SMA</SelectItem>
                <SelectItem value="ema">EMA</SelectItem>
                <SelectItem value="wma">WMA</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </>
      )}
    </div>
  );
}
