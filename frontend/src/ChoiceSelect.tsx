import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type ChoiceSelectProps = {
  value?: string;
  defaultValue?: string;
  disabled?: boolean;
  id: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  options: readonly { value: string; label: string }[];
  className?: string;
};

export function ChoiceSelect({
  id,
  placeholder,
  options,
  className,
  onValueChange,
  ...props
}: ChoiceSelectProps) {
  return (
    <Select<string>
      {...props}
      items={options}
      onValueChange={(value) => {
        if (value !== null) onValueChange?.(value);
      }}
    >
      <SelectTrigger
        id={id}
        className={`choice-select w-full ${className || ""}`}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent alignItemWithTrigger={false} align="start">
        {options.map(({ value, label }) => (
          <SelectItem key={value} value={value}>
            {label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
