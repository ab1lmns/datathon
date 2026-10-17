import type { CSSProperties } from 'react';
import { ArrowUpRight, type AppIcon } from './Icons';

type FolderCardProps = {
  title: string;
  value: number | null;
  subtitle: string;
  Icon: AppIcon;
  color: string;
  order: number;
  selected: boolean;
  onClick: (source: HTMLButtonElement) => void;
};

export function FolderCard({ title, value, subtitle, Icon, color, order, selected, onClick }: FolderCardProps) {
  return <button
    className={`folder ${color}`}
    data-reveal
    style={{ '--order': order } as CSSProperties}
    aria-pressed={selected}
    onClick={event => onClick(event.currentTarget)}
  >
    <span className="folder-back" aria-hidden="true"/>
    <span className="folder-sheet folder-sheet-back" aria-hidden="true"/>
    <span className="folder-sheet folder-sheet-top" aria-hidden="true"/>
    <span className="folder-front">
      <span className="folder-icon"><Icon size={21}/></span>
      <ArrowUpRight className="folder-arrow" size={16} aria-hidden="true"/>
      <strong>{title}</strong>
      <span className="folder-meta">{value !== null && <b>{value.toString().padStart(2, '0')}</b>}{subtitle}</span>
    </span>
  </button>;
}
