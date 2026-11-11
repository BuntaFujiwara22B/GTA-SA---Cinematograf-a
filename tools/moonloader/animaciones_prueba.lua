script_name('AnimacionesPrueba')
require 'lib.moonloader'
local keys = require 'vkeys'
local ffi = require 'ffi'
local memory = require 'memory'

-- Captura igual que los scripts existentes: Windows guarda los PNG.
pcall(ffi.cdef, [[
    void keybd_event(unsigned char, unsigned char, unsigned long, unsigned long);
]])
local user32 = ffi.load('user32')
local MODELO = 7
local EMPEZAR_EN = 1
local ESPERA_POSE_MS = 700
local ESPERA_GUARDADO_MS = 2000
local POSES = {0.05, 0.23, 0.41, 0.59, 0.77, 0.95}
-- Categoria, indice ORIGINAL de todo.txt, animacion, biblioteca.
local ANIMACIONES = {
    {'STAND', 1, 'handsup', 'ped'},
    {'STAND', 2, 'roadcross', 'ped'},
    {'STAND', 3, 'graffiti_Chkout', 'graffiti'},
    {'CHAT', 1, 'endchat_01', 'ped'},
    {'CHAT', 2, 'endchat_02', 'ped'},
    {'DANCE', 1, 'bd_clap', 'DANCING'},
    {'DANCE', 2, 'bd_clap1', 'DANCING'},
    {'HURT', 1, 'Bat_Hit_1', 'BASEBALL'},
    {'MOVE', 2, 'EV_dive', 'ped'},
    {'DEATH', 1, 'crckdeth1', 'CRACK'},
}

local ped, archivo, biblioteca
local activo = false
local cancelado = false
local numeroCaptura = 0

-- GTA SA 1.0 US, igual que el capturador previo de esta instalacion.
-- No usar PLAYER_PED: el mod puede dejar ese handle desactualizado.
local function posicionJugador()
    local ptr = memory.getuint32(0xB6F5F0, true)
    if not ptr or ptr == 0 then return nil end
    local matriz = memory.getuint32(ptr + 0x14, true)
    local x, y, z
    if matriz ~= 0 then
        x = memory.getfloat(matriz + 0x30, true)
        y = memory.getfloat(matriz + 0x34, true)
        z = memory.getfloat(matriz + 0x38, true)
    else
        x = memory.getfloat(ptr + 0x04, true)
        y = memory.getfloat(ptr + 0x08, true)
        z = memory.getfloat(ptr + 0x0C, true)
    end
    local h = math.deg(memory.getfloat(ptr + 0x558, true)) % 360
    for _, v in ipairs({x, y, z, h}) do
        if v ~= v or math.abs(v) >= 10000 then return nil end
    end
    return x, y, z, h
end

local function esperar(ms)
    local inicio = getGameTimer()
    repeat
        wait(0)
        if isKeyDown(keys.VK_F9) then
            cancelado = true
            error('CANCELADO', 0)
        end
    until getGameTimer() - inicio >= ms
end

local function liberarPed()
    if ped then pcall(deleteChar, ped); ped = nil end
    if biblioteca and biblioteca:lower() ~= 'ped' then
        pcall(removeAnimation, biblioteca)
    end
    biblioteca = nil
end

local function restaurar()
    liberarPed()
    pcall(restoreCameraJumpcut)
    pcall(displayHud, true)
    pcall(displayRadar, true)
    pcall(markModelAsNoLongerNeeded, MODELO)
    -- Soltar teclas incluso si se interrumpe durante la captura.
    pcall(function()
        user32.keybd_event(0x2C, 0, 2, 0)
        user32.keybd_event(0x5B, 0, 2, 0)
    end)
    if archivo then archivo:flush(); archivo:close(); archivo = nil end
    activo = false
end

local function campo(valor)
    return '"' .. tostring(valor or ''):gsub('"', '""') .. '"'
end

local function registrar(orden, a, frame, fase, estado, detalle)
    local nombre = string.format('%s_%03d_%s_%s_f%d.png',
        a[1], a[2], a[4], a[3], frame)
    local valores = {orden, a[1], a[2], a[3], a[4], frame,
        fase, numeroCaptura, nombre, estado, detalle or ''}
    for i, v in ipairs(valores) do valores[i] = campo(v) end
    archivo:write(table.concat(valores, ',') .. '\n')
    archivo:flush()
end

local function capturar()
    user32.keybd_event(0x5B, 0, 0, 0)
    user32.keybd_event(0x2C, 0, 0, 0)
    -- No usar esperar aqui: soltar las teclas antes de atender F9.
    wait(80)
    user32.keybd_event(0x2C, 0, 2, 0)
    user32.keybd_event(0x5B, 0, 2, 0)
    numeroCaptura = numeroCaptura + 1
end

local function cargarBiblioteca(lib)
    biblioteca = lib
    -- ped es la biblioteca residente: no pedir ni descargar ped.ifp.
    if lib:lower() == 'ped' then return end
    requestAnimation(lib)
    local inicio = getGameTimer()
    while not hasAnimationLoaded(lib) do
        if getGameTimer() - inicio > 5000 then error('Biblioteca no disponible: ' .. lib) end
        esperar(25)
    end
end

local function probar(orden, a, x, y, z, heading)
    cargarBiblioteca(a[4])
    ped = createChar(4, MODELO, x, y, z)
    if not ped or not doesCharExist(ped) then error('No se pudo crear el NPC') end
    setCharHeading(ped, (heading + 180) % 360)
    esperar(300)
    -- Bloquear desplazamiento XY para conservar el encuadre, no las extremidades.
    taskPlayAnim(ped, a[3], a[4], 8.0, true, true, true, true, -1)
    local inicio = getGameTimer()
    while not isCharPlayingAnim(ped, a[3]) do
        if getGameTimer() - inicio > 2000 then error('La animacion no comenzo') end
        esperar(0)
    end
    setCharAnimSpeed(ped, a[3], 0.0)
    for frame, fase in ipairs(POSES) do
        if not isCharPlayingAnim(ped, a[3]) then error('Animacion interrumpida') end
        setCharAnimCurrentTime(ped, a[3], fase)
        -- Reafirmar la camara por si otro script la cambio entre tomas.
        local r = math.rad(heading)
        setFixedCameraPosition(x + 5 * math.sin(r), y - 5 * math.cos(r), z + 0.3, 0, 0, 0)
        pointCameraAtPoint(x, y, z - 0.2, 2)
        esperar(ESPERA_POSE_MS)
        capturar()
        -- SOLICITADA no significa que Windows haya confirmado el archivo.
        registrar(orden, a, frame, fase, 'SOLICITADA', '')
        esperar(ESPERA_GUARDADO_MS)
    end
end

local function ejecutar()
    cancelado = false
    numeroCaptura = 0
    local x, y, z, h = posicionJugador()
    if not x then error('Jugador no disponible: carga la partida y sal de los menus') end
    print(string.format('[AnimacionesPrueba] Jugador: %.2f %.2f %.2f rumbo %.2f', x, y, z, h))
    local nombre = getWorkingDirectory() .. '\\animaciones_prueba_' .. os.date('%Y%m%d_%H%M%S') .. '.csv'
    -- Evitar reemplazar un registro previo, incluso con el mismo segundo.
    local previo = io.open(nombre, 'r')
    if previo then previo:close(); error('Ya existe el CSV; espera un segundo y repite') end
    archivo = assert(io.open(nombre, 'w'))
    archivo:write('orden,categoria,idx,anim,lib,frame,fase,solicitud,nombre_destino,estado,detalle\n')
    archivo:flush()
    print('[AnimacionesPrueba] CSV: ' .. nombre)

    local r = math.rad(h)
    local fx, fy = -math.sin(r), math.cos(r)
    local ax, ay = x + 8 * fx, y + 8 * fy
    -- Misma altura que el jugador: elegir terreno plano y abierto.
    setFixedCameraPosition(ax - 5 * fx, ay - 5 * fy, z + 0.3, 0, 0, 0)
    pointCameraAtPoint(ax, ay, z - 0.2, 2)
    displayHud(false)
    displayRadar(false)
    requestModel(MODELO)
    loadAllModelsNow()
    local inicio = getGameTimer()
    while not hasModelLoaded(MODELO) do
        if getGameTimer() - inicio > 5000 then error('No cargo el modelo del NPC') end
        esperar(25)
    end
    esperar(700)
    for orden = EMPEZAR_EN, #ANIMACIONES do
        local a = ANIMACIONES[orden]
        print(string.format('[AnimacionesPrueba] %d/10 %s %s', orden, a[4], a[3]))
        local ok, err = pcall(probar, orden, a, ax, ay, z, h)
        liberarPed()
        if not ok then
            registrar(orden, a, 0, 0, cancelado and 'CANCELADA' or 'ERROR', err)
            print('[AnimacionesPrueba] ' .. tostring(err))
            if cancelado then break end
        end
        esperar(200)
    end
end

function main()
    while posicionJugador() == nil do wait(100) end
    printStringNow('~Y~Animaciones: F8 iniciar / F9 cancelar', 5000)
    while true do
        wait(0)
        if wasKeyPressed(keys.VK_F8) and not activo then
            activo = true
            cancelado = false
            numeroCaptura = 0
            printStringNow('~Y~Preparando prueba: no toques los controles', 2000)
            local ok, err = pcall(function() esperar(2500); ejecutar() end)
            local cantidad = numeroCaptura
            restaurar()
            if not ok then print('[AnimacionesPrueba] ' .. tostring(err)) end
            printStringNow(string.format('~Y~%s: %d capturas solicitadas. Revisar CSV.',
                cancelado and 'Cancelado' or (ok and 'Terminado' or 'Error'), cantidad), 6000)
        end
    end
end

function onScriptTerminate(script, quitGame)
    if script == thisScript() and activo then restaurar() end
end
