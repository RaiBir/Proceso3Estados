"""
Simulador del Ciclo de Vida de Procesos de 3 Estados (Listo, Ejecutando, Bloqueado)
Asignatura: Sistemas Operativos (NRC 5120)
Descripción: Emulación interactiva del planificador de CPU de corto plazo (Despachador)
             bajo una política Round Robin con soporte para interrupciones por Quantum
             y bloqueos por solicitudes de Entrada/Salida (E/S).
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime

class Proceso:
    """
    Clase que representa el Bloque de Control de Proceso (PCB - Process Control Block).
    Almacena el identificador, tiempos de CPU, estado actual y métricas de cambios de contexto.
    """
    def __init__(self, nombre: str, tiempo_irrupcion: int):
        self.nombre = nombre
        self.tiempo_total = tiempo_irrupcion       # Tiempo total de CPU requerido (ráfaga)
        self.tiempo_restante = tiempo_irrupcion    # Tiempo que le falta para terminar
        self.estado = "Listo"                      # Estado inicial en el modelo de 3 estados
        self.cambios_contexto = 0                  # Contador de veces que sale de la CPU
        self.interrupciones_quantum = 0            # Contador de expropiaciones por tiempo
        self.bloqueos_es = 0                       # Contador de bloqueos voluntarios por E/S

    def __repr__(self):
        return f"Proceso({self.nombre}, Restante={self.tiempo_restante}s, Estado={self.estado})"


class SimuladorTresEstados:
    """
    Clase principal que gestiona las colas de estados, las transiciones del despachador
    y la interfaz gráfica de usuario (GUI).
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador del Modelo de 3 Estados - Sistemas Operativos")
        self.root.geometry("950x680")
        self.root.configure(bg="#1e1e2e")

        # Parámetros del planificador
        self.quantum = 3  # Tiempo máximo de CPU por turno (en unidades de tiempo)

        # Vectores / Colas de estados
        self.cola_listos = []          # Vector FIFO de procesos en estado Listo
        self.proceso_ejecutando = None # Proceso actualmente en uso de la CPU
        self.cola_bloqueados = []      # Vector FIFO de procesos esperando E/S
        self.procesos_terminados = []  # Registro histórico para métricas finales
        self.todos_los_procesos = []   # Referencia general a los procesos A, B y C

        # Construcción de la interfaz y carga inicial
        self._construir_interfaz()
        self.inicializar_procesos()

        # Enlace de la tecla Enter para bloquear el proceso en ejecución por E/S
        self.root.bind('<Return>', self.evento_tecla_enter)

    def _construir_interfaz(self):
        """Inicializa todos los componentes visuales de la ventana."""
        # Título y configuración de Quantum
        frame_top = tk.Frame(self.root, bg="#1e1e2e")
        frame_top.pack(fill=tk.X, padx=15, pady=10)

        lbl_titulo = tk.Label(
            frame_top, text="EMULADOR DE PLANIFICACIÓN DE CPU - MODELO DE 3 ESTADOS",
            font=("Segoe UI", 14, "bold"), fg="#cdd6f4", bg="#1e1e2e"
        )
        lbl_titulo.pack(side=tk.LEFT)

        frame_q = tk.Frame(frame_top, bg="#1e1e2e")
        frame_q.pack(side=tk.RIGHT)
        tk.Label(frame_q, text="Quantum (u.t.):", font=("Segoe UI", 10, "bold"), fg="#a6adc8", bg="#1e1e2e").pack(side=tk.LEFT, padx=5)
        self.spin_quantum = tk.Spinbox(frame_q, from_=1, to=10, width=5, font=("Segoe UI", 10), command=self.actualizar_quantum)
        self.spin_quantum.delete(0, "end")
        self.spin_quantum.insert(0, str(self.quantum))
        self.spin_quantum.pack(side=tk.LEFT)

        # Panel central con las 3 columnas de estados
        frame_estados = tk.Frame(self.root, bg="#1e1e2e")
        frame_estados.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # 1. Columna Estado LISTO
        frame_listo = tk.LabelFrame(
            frame_estados, text=" 1. COLA DE LISTOS (Vector FIFO) ",
            font=("Segoe UI", 11, "bold"), fg="#a6e3a1", bg="#313244", bd=2
        )
        frame_listo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.lista_listos_ui = tk.Listbox(frame_listo, font=("Consolas", 11), bg="#181825", fg="#cdd6f4", selectbackground="#45475a", height=8)
        self.lista_listos_ui.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 2. Columna Estado EJECUTANDO
        frame_ejec = tk.LabelFrame(
            frame_estados, text=" 2. EJECUTANDO (CPU) ",
            font=("Segoe UI", 11, "bold"), fg="#f9e2af", bg="#313244", bd=2
        )
        frame_ejec.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.lbl_ejecutando = tk.Label(
            frame_ejec, text="[ CPU INACTIVA ]", font=("Consolas", 12, "bold"),
            fg="#f38ba8", bg="#181825", justify=tk.CENTER, relief=tk.SUNKEN, bd=1
        )
        self.lbl_ejecutando.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 3. Columna Estado BLOQUEADO
        frame_bloq = tk.LabelFrame(
            frame_estados, text=" 3. BLOQUEADO (Espera de E/S) ",
            font=("Segoe UI", 11, "bold"), fg="#fab387", bg="#313244", bd=2
        )
        frame_bloq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.lista_bloq_ui = tk.Listbox(frame_bloq, font=("Consolas", 11), bg="#181825", fg="#cdd6f4", selectbackground="#45475a", height=8)
        self.lista_bloq_ui.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Panel de Botones de Transición (Eventos del Sistema)
        frame_botones = tk.LabelFrame(
            self.root, text=" Panel de Control de Transiciones (Despachador e Interrupciones) ",
            font=("Segoe UI", 10, "bold"), fg="#89b4fa", bg="#313244", bd=2
        )
        frame_botones.pack(fill=tk.X, padx=15, pady=8)

        # Botón Transición 1: Listo -> Ejecutando
        self.btn_despachar = tk.Button(
            frame_botones, text="▶ 1. Despachar (Listo → Ejecutando)",
            font=("Segoe UI", 10, "bold"), bg="#a6e3a1", fg="#11111b", padx=10, pady=6,
            command=self.transicion_listo_a_ejecutando
        )
        self.btn_despachar.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        # Botón Transición 2: Ejecutando -> Listo (Expiración de Quantum / Fin de ráfaga)
        self.btn_quantum = tk.Button(
            frame_botones, text="⏱ 2. Consumir Quantum / Interrumpir (Ejecutando → Listo)",
            font=("Segoe UI", 10, "bold"), bg="#f9e2af", fg="#11111b", padx=10, pady=6,
            command=self.transicion_ejecutando_a_listo
        )
        self.btn_quantum.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        # Botón Transición 3: Ejecutando -> Bloqueado (Solicitud E/S o Tecla Enter)
        self.btn_bloquear = tk.Button(
            frame_botones, text="⏸ 3. Solicitar E/S [o Enter] (Ejecutando → Bloqueado)",
            font=("Segoe UI", 10, "bold"), bg="#fab387", fg="#11111b", padx=10, pady=6,
            command=self.transicion_ejecutando_a_bloqueado
        )
        self.btn_bloquear.grid(row=1, column=0, padx=8, pady=8, sticky="ew")

        # Botón Transición 4: Bloqueado -> Listo (Fin de E/S)
        self.btn_despertar = tk.Button(
            frame_botones, text="🔄 4. Completar Evento E/S (Bloqueado → Último en Listo)",
            font=("Segoe UI", 10, "bold"), bg="#89dceb", fg="#11111b", padx=10, pady=6,
            command=self.transicion_bloqueado_a_listo
        )
        self.btn_despertar.grid(row=1, column=1, padx=8, pady=8, sticky="ew")

        # Botón de Reinicio
        btn_reiniciar = tk.Button(
            frame_botones, text="🔁 Reiniciar Procesos (A, B, C)",
            font=("Segoe UI", 10, "bold"), bg="#f38ba8", fg="#11111b", padx=10, pady=6,
            command=self.inicializar_procesos
        )
        btn_reiniciar.grid(row=0, column=2, rowspan=2, padx=8, pady=8, sticky="ns")

        frame_botones.columnconfigure(0, weight=1)
        frame_botones.columnconfigure(1, weight=1)

        # Bitácora / Log de Eventos y Estadísticas
        frame_inferior = tk.Frame(self.root, bg="#1e1e2e")
        frame_inferior.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        frame_log = tk.LabelFrame(
            frame_inferior, text=" Bitácora de Transiciones e Interrupciones en Tiempo Real ",
            font=("Segoe UI", 10, "bold"), fg="#cba6f7", bg="#313244"
        )
        frame_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.txt_log = scrolledtext.ScrolledText(frame_log, font=("Consolas", 9), bg="#11111b", fg="#cdd6f4", height=9)
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        frame_stats = tk.LabelFrame(
            frame_inferior, text=" Métricas de PCB (Cambios de Contexto) ",
            font=("Segoe UI", 10, "bold"), fg="#f5c2e7", bg="#313244", width=300
        )
        frame_stats.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        self.lbl_stats = tk.Label(
            frame_stats, text="", font=("Consolas", 10), fg="#cdd6f4", bg="#181825", justify=tk.LEFT, anchor="nw", padx=10, pady=10
        )
        self.lbl_stats.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def registrar_evento(self, mensaje: str):
        """Agrega una línea con marca de tiempo a la bitácora del simulador."""
        hora = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{hora}] {mensaje}\n")
        self.txt_log.see(tk.END)

    def actualizar_quantum(self):
        """Actualiza el valor del Quantum desde el control numérico."""
        try:
            self.quantum = int(self.spin_quantum.get())
            self.registrar_evento(f"Configuración: Quantum ajustado a {self.quantum} u.t.")
        except ValueError:
            pass

    def inicializar_procesos(self):
        """Crea los procesos A, B y C con diferentes tiempos de ráfaga y los encola en Listo."""
        self.cola_listos.clear()
        self.cola_bloqueados.clear()
        self.procesos_terminados.clear()
        self.proceso_ejecutando = None

        # Creación de los 3 procesos iniciales A, B y C
        p_a = Proceso("Proceso A", tiempo_irrupcion=7)
        p_b = Proceso("Proceso B", tiempo_irrupcion=5)
        p_c = Proceso("Proceso C", tiempo_irrupcion=8)

        self.todos_los_procesos = [p_a, p_b, p_c]
        self.cola_listos.extend(self.todos_los_procesos)

        self.txt_log.delete(1.0, tk.END)
        self.registrar_evento("=== SIMULACIÓN INICIADA ===")
        self.registrar_evento(f"Procesos A (7 u.t.), B (5 u.t.) y C (8 u.t.) cargados en la Cola de Listos.")
        self.actualizar_vista()

    def transicion_listo_a_ejecutando(self):
        """
        Transición 1: LISTO -> EJECUTANDO.
        El despachador selecciona el primer proceso de la cola de listos y le asigna la CPU.
        """
        if self.proceso_ejecutando is not None:
            messagebox.showwarning(
                "CPU Ocupada",
                f"El {self.proceso_ejecutando.nombre} ya está en EJECUTANDO.\n"
                "Debes interrumpirlo por Quantum o bloquearlo por E/S antes de despachar otro."
            )
            return

        if not self.cola_listos:
            messagebox.showinfo("Cola de Listos Vacía", "No hay procesos en la cola de Listos para despachar.")
            return

        # Sacar el primer proceso del vector de listos (FIFO)
        self.proceso_ejecutando = self.cola_listos.pop(0)
        self.proceso_ejecutando.estado = "Ejecutando"

        self.registrar_evento(
            f"[DESPACHADOR] Transición Listo -> Ejecutando: '{self.proceso_ejecutando.nombre}' "
            f"toma la CPU (Restante: {self.proceso_ejecutando.tiempo_restante} u.t., Quantum asignado: {self.quantum} u.t.)."
        )
        self.actualizar_vista()

    def transicion_ejecutando_a_listo(self):
        """
        Transición 2: EJECUTANDO -> LISTO (Expropiación por Quantum o finalización de tarea).
        Descuenta el tiempo del Quantum. Si el tiempo no fue suficiente, genera una interrupción
        de reloj y envía el proceso al final del vector de Listos.
        """
        if self.proceso_ejecutando is None:
            messagebox.showwarning("CPU Inactiva", "No hay ningún proceso en estado EJECUTANDO.")
            return

        proc = self.proceso_ejecutando
        self.actualizar_quantum()

        # Evaluar si el Quantum es suficiente para terminar o si ocurre interrupción
        if proc.tiempo_restante > self.quantum:
            proc.tiempo_restante -= self.quantum
            proc.estado = "Listo"
            proc.cambios_contexto += 1
            proc.interrupciones_quantum += 1

            # Regresa al final del vector de la cola de procesos listos
            self.cola_listos.append(proc)
            self.registrar_evento(
                f"[INTERRUPCIÓN POR QUANTUM] Transición Ejecutando -> Listo: '{proc.nombre}' "
                f"ejecutó {self.quantum} u.t. Tiempo insuficiente (Restante: {proc.tiempo_restante} u.t.). "
                f"Encolado al final de Listos."
            )
        else:
            # El tiempo le alcanzó para completar su ejecución
            tiempo_usado = proc.tiempo_restante
            proc.tiempo_restante = 0
            proc.estado = "Terminado"
            proc.cambios_contexto += 1
            self.procesos_terminados.append(proc)
            self.registrar_evento(
                f"[PROCESO COMPLETADO] '{proc.nombre}' ejecutó {tiempo_usado} u.t. restantes y finalizó su ciclo."
            )

        self.proceso_ejecutando = None
        self.actualizar_vista()

    def transicion_ejecutando_a_bloqueado(self):
        """
        Transición 3: EJECUTANDO -> BLOQUEADO.
        El proceso solicita una operación de E/S o espera un evento antes de agotar su Quantum.
        Consume parcialmente CPU (1 u.t.), cede la CPU voluntariamente y pasa a Bloqueado.
        """
        if self.proceso_ejecutando is None:
            messagebox.showwarning("CPU Inactiva", "No hay ningún proceso en estado EJECUTANDO para bloquear.")
            return

        proc = self.proceso_ejecutando
        # Simula que avanzó 1 unidad de tiempo antes de pedir la operación de E/S
        if proc.tiempo_restante > 1:
            proc.tiempo_restante -= 1

        proc.estado = "Bloqueado"
        proc.cambios_contexto += 1
        proc.bloqueos_es += 1

        self.cola_bloqueados.append(proc)
        self.registrar_evento(
            f"[SOLICITUD DE E/S] Transición Ejecutando -> Bloqueado: '{proc.nombre}' "
            f"solicitó un dispositivo de E/S (Restante: {proc.tiempo_restante} u.t.). Pasa a espera."
        )

        self.proceso_ejecutando = None

        # Si hay otro proceso en la cola de listos, notificar que el despachador puede darle paso
        if self.cola_listos:
            siguiente = self.cola_listos[0].nombre
            self.registrar_evento(
                f"  -> CPU libre. El proceso '{siguiente}' está primero en Listos esperando ser despachado."
            )

        self.actualizar_vista()

    def transicion_bloqueado_a_listo(self):
        """
        Transición 4: BLOQUEADO -> LISTO.
        Ocurre cuando el dispositivo de E/S termina la operación. El proceso sale de Bloqueado
        y se inserta en el último lugar del vector de la cola de procesos Listos.
        """
        if not self.cola_bloqueados:
            messagebox.showinfo("Sin Procesos Bloqueados", "No hay procesos en el estado BLOQUEADO actualmente.")
            return

        proc = self.cola_bloqueados.pop(0)
        proc.estado = "Listo"
        self.cola_listos.append(proc)

        self.registrar_evento(
            f"[FIN DE E/S] Transición Bloqueado -> Listo: '{proc.nombre}' recibió su evento de E/S "
            f"y se ubicó al final de la Cola de Listos (Posición {len(self.cola_listos)})."
        )
        self.actualizar_vista()

    def evento_tecla_enter(self, event):
        """Manejador para que la tecla Enter dispare el bloqueo por E/S cuando hay un proceso en CPU."""
        if self.proceso_ejecutando is not None:
            self.transicion_ejecutando_a_bloqueado()

    def actualizar_vista(self):
        """Refresca las listas visuales y el cuadro de estadísticas."""
        # Actualizar Listbox de Listos
        self.lista_listos_ui.delete(0, tk.END)
        for idx, p in enumerate(self.cola_listos, start=1):
            self.lista_listos_ui.insert(tk.END, f" {idx}. {p.nombre} | Restante: {p.tiempo_restante}/{p.tiempo_total} u.t.")

        # Actualizar etiqueta de Ejecutando
        if self.proceso_ejecutando:
            p = self.proceso_ejecutando
            texto_cpu = (
                f"⚡ {p.nombre.upper()} EN CPU ⚡\n\n"
                f"Tiempo Total:    {p.tiempo_total} u.t.\n"
                f"Tiempo Restante: {p.tiempo_restante} u.t.\n"
                f"Quantum Actual:  {self.quantum} u.t.\n\n"
                f"[Presiona ENTER para Bloquear por E/S]"
            )
            self.lbl_ejecutando.config(text=texto_cpu, fg="#a6e3a1")
        else:
            self.lbl_ejecutando.config(text="[ CPU INACTIVA ]\n\nHaz clic en 'Despachar'\npara cargar un proceso", fg="#f38ba8")

        # Actualizar Listbox de Bloqueados
        self.lista_bloq_ui.delete(0, tk.END)
        for idx, p in enumerate(self.cola_bloqueados, start=1):
            self.lista_bloq_ui.insert(tk.END, f" {idx}. {p.nombre} | Esperando E/S (Rest: {p.tiempo_restante} u.t.)")

        # Actualizar panel de estadísticas
        lineas_stats = ["PROCESO  | CTX | Q-INT | E/S | ESTADO", "-" * 42]
        for p in self.todos_los_procesos:
            lineas_stats.append(
                f"{p.nombre:<8} |  {p.cambios_contexto:<2} |   {p.interrupciones_quantum:<3} |  {p.bloqueos_es:<2} | {p.estado}"
            )
        lineas_stats.append("-" * 42)
        lineas_stats.append("CTX: Cambios de Contexto totales")
        lineas_stats.append("Q-INT: Interrupciones por Quantum")
        lineas_stats.append("E/S: Bloqueos por Entrada/Salida")
        self.lbl_stats.config(text="\n".join(lineas_stats))


if __name__ == "__main__":
    ventana = tk.Tk()
    app = SimuladorTresEstados(ventana)
    ventana.mainloop()
