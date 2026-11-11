script_name('ComprobarRutaMVP')
require 'lib.moonloader'
local memory=require 'memory'
-- Debe coincidir con la carpeta del proyecto. No modifica el jugador ni la camara.
local BASE='C:/Users/Danilo/Downloads/simulador_cinematografico/ruta_mvp/'
local ultimo=''

local function responder(id,estado,mensaje)
    local f=io.open(BASE..'respuesta.tmp','w')
    if not f then return end
    f:write(string.format('{"id":"%s","estado":"%s","mensaje":"%s"}',id,estado,mensaje))
    f:close()
    os.remove(BASE..'respuesta.json')
    os.rename(BASE..'respuesta.tmp',BASE..'respuesta.json')
end

local function posicion()
    local p=memory.getuint32(0xB6F5F0,true)
    if not p or p==0 then return nil end
    local m=memory.getuint32(p+0x14,true)
    if not m or m==0 then return nil end
    return memory.getfloat(m+0x30,true),memory.getfloat(m+0x34,true),memory.getfloat(m+0x38,true)
end

local function comprobar(linea)
    local partes={}
    for s in linea:gmatch('[^,]+') do partes[#partes+1]=s end
    local id=partes[1]
    if #partes~=7 or not id:match('^[a-f0-9]+$') or #id~=32 then return end
    if id==ultimo then return end
    ultimo=id
    local v={}
    for i=2,7 do
        local n=tonumber(partes[i])
        if not n or n~=n or math.abs(n)>10000 then responder(id,'error','Coordenadas no validas.'); return end
        v[i-1]=n
    end
    local px,py,pz=posicion()
    if not px then responder(id,'sin_comprobar','Carga una partida de GTA y sal del menu.'); return end
    local ax,ay,az,bx,by,bz=unpack(v)
    -- No dar por libres las colisiones de zonas que no estan cargadas.
    if math.sqrt((px-ax)^2+(py-ay)^2)>150 or math.sqrt((px-bx)^2+(py-by)^2)>150 then
        responder(id,'sin_comprobar','Situa al jugador a menos de 150 metros de ambos puntos para cargar la zona.'); return
    end
    local dx,dy=bx-ax,by-ay
    local distancia=math.sqrt(dx*dx+dy*dy)
    if distancia<2 or distancia>150 then responder(id,'error','El recorrido debe medir de 2 a 150 metros.'); return end
    local nx,ny=-dy/distancia,dx/distancia
    local pasos=math.ceil(distancia/2)
    for i=0,pasos-1 do
        local t1,t2=i/pasos,(i+1)/pasos
        for _,lateral in ipairs({-0.3,0,0.3}) do
            for _,altura in ipairs({0.35,0.9,1.5}) do
                local libre=isLineOfSightClear(
                    ax+dx*t1+nx*lateral,ay+dy*t1+ny*lateral,az+(bz-az)*t1+altura,
                    ax+dx*t2+nx*lateral,ay+dy*t2+ny*lateral,az+(bz-az)*t2+altura,
                    true,true,false,true,true)
                if not libre then
                    responder(id,'bloqueada','Hay una colision en medio de la ruta. Cambia inicio o destino para evitar el obstaculo.'); return
                end
            end
        end
        wait(0)
    end
    responder(id,'libre','GTA no detecto colisiones en las lineas comprobadas. Los obstaculos moviles pueden cambiar. ')
end

function main()
    while true do
        wait(250)
        local f=io.open(BASE..'solicitud.txt','r')
        if f then
            local linea=f:read('*l'); f:close()
            if linea then
                local ok,err=pcall(comprobar,linea)
                if not ok then
                    print('[ComprobarRutaMVP] '..tostring(err))
                    if #ultimo==32 then responder(ultimo,'error','No se pudo consultar la colision. Revisa moonloader.log.'); end
                end
            end
        end
    end
end
