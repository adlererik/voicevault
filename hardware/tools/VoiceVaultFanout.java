// SPDX-License-Identifier: GPL-3.0-or-later
// Experimental FreeRouting public-API driver; native qualification is mandatory.
import app.freerouting.io.specctra.DsnReader;
import app.freerouting.io.specctra.SesWriter;
import app.freerouting.io.BoardReadResult;
import app.freerouting.board.facade.RoutingBoard;
import app.freerouting.board.model.items.Pin;
import app.freerouting.autoroute.AutorouteAttemptState;
import app.freerouting.autoroute.pipeline.BatchAutorouter;
import app.freerouting.datastructures.TimeLimit;
import app.freerouting.settings.sources.DefaultSettings;
import com.google.gson.GsonBuilder;
import java.nio.file.*;
import java.util.*;

/** Copy-only targeted fanout driver using the official, unmodified FreeRouting library.
 * No manually supplied trace coordinates. No live KiCad writes. Native qualification
 * of the resulting SES is mandatory; a library ROUTED status is not design approval.
 */
public class VoiceVaultFanout {
  public static void main(String[] args) throws Exception {
    if (args.length != 4 && args.length != 5) throw new IllegalArgumentException("DSN OUTPUT_SES COMPONENTS_CSV PASSES [MIN_ESCAPE_MM] (zero passes = read-only check)");
    var input=Path.of(args[0]); var output=Path.of(args[1]);
    var allowed=new LinkedHashSet<>(Arrays.asList(args[2].split(",")));
    int passes=Integer.parseInt(args[3]); if(passes<0||passes>100)throw new IllegalArgumentException("Pass count out of range");
    var result=DsnReader.readBoard(Files.newInputStream(input),null,null,input.getFileName().toString());
    if(!(result instanceof BoardReadResult.Success success))throw new IllegalStateException("Native DSN read failed: "+result);
    var board=(RoutingBoard)success.board();
    var settings=new DefaultSettings().getSettings();
    settings.setLayerCount(board.getLayerCount());
    settings.applyBoardSpecificOptimizations(board);
    settings.planeAsObstacle=false;settings.planeNets=new String[]{"GND"};
    board.changePlaneAsObstacle(false); // Direct DsnReader does not apply the headless manager override.
    settings.strictDrc=true;settings.neckWidthUm=100.0;settings.automaticNeckdown=false;
    settings.copperToEdgeClearanceUm=500.0;settings.holeClearanceUm=250.0;
    int holeUnits=(int)Math.round(app.freerouting.board.model.structure.Unit.scale(
      250.0*Math.max(1,board.communication.resolution),app.freerouting.board.model.structure.Unit.UM,board.communication.unit));
    board.rules.setHoleClearance(holeUnits);
    board.searchTreeManager.reinsertTreeItems();
    settings.fanout.enabled=true;settings.fanout.minEscapeLengthMm=args.length==5?Double.parseDouble(args[4]):0.6;
    if(!Double.isFinite(settings.fanout.minEscapeLengthMm)||settings.fanout.minEscapeLengthMm<0||settings.fanout.minEscapeLengthMm>4.5)throw new IllegalArgumentException("Escape minimum out of range");
    settings.fanout.maxEscapeLengthMm=4.5;settings.fanout.startViaDiameterMm=0.25;
    settings.fanout.endViaDiameterMm=0.45;settings.fanout.fallbackToBoardVias=true;
    settings.fanout.ripupAllowed=false;settings.fanout.pinSortingOrder="inner_first";
    var pins=new ArrayList<Pin>();var seen=new TreeSet<String>();
    for(var p:board.getSmdPins()){
      var component=board.components.get(p.getComponentId());
      if(component!=null&&allowed.contains(component.name)&&p.netCount()==1){pins.add(p);seen.add(component.name);}
    }
    if(!seen.equals(new TreeSet<>(allowed)))throw new IllegalArgumentException("Requested components missing: "+seen+" vs "+allowed);
    var centers=new HashMap<Integer,double[]>();
    for(var p:pins){var xy=p.getCenter().toFloat();var c=centers.computeIfAbsent(p.getComponentId(),k->new double[3]);c[0]+=xy.x;c[1]+=xy.y;c[2]++;}
    for(var c:centers.values()){c[0]/=c[2];c[1]/=c[2];}
    pins.sort(Comparator.comparing((Pin p)->board.components.get(p.getComponentId()).name)
      .thenComparingDouble(p->{var xy=p.getCenter().toFloat();var c=centers.get(p.getComponentId());return Math.hypot(xy.x-c[0],xy.y-c[1]);}).thenComparing(Pin::name));
    var gson=new GsonBuilder().setPrettyPrinting().create();
    System.out.println("Targeted fanout: "+pins.size()+" connected SMD pins in "+seen+"; passes="+passes+"; ripup disabled");
    var attempts=new ArrayList<Map<String,Object>>();int completed=0;
    for(int pass=0;pass<passes;pass++){
      int routed=0;
      for(var pin:pins){
        String ref=board.components.get(pin.getComponentId()).name;
        int oldMaxId=board.communication.idGenerator.maxGeneratedId();
        board.startMarkingChangedArea();
        var start=System.nanoTime();
        var answer=board.fanout(pin,settings,-1,null,new TimeLimit(10000*(pass+1)));
        if(answer.state==AutorouteAttemptState.ROUTED){
          var rejected=BatchAutorouter.enforceStrictDrc(board,pin.getNetNumber(0),oldMaxId);
          if(rejected!=null)answer=rejected;else routed++;
        }
        var row=new LinkedHashMap<String,Object>();row.put("pass",pass+1);row.put("component",ref);row.put("pin",pin.name());row.put("state",answer.state.toString());row.put("detail",answer.details);row.put("milliseconds",(System.nanoTime()-start)/1000000);attempts.add(row);
        if(answer.state!=AutorouteAttemptState.ALREADY_CONNECTED&&answer.state!=AutorouteAttemptState.NO_UNCONNECTED_NETS)System.out.println(ref+"-"+pin.name()+": "+answer.state+" "+answer.details);
      }
      completed++;
      // Save an observable checkpoint after every complete pass, even if later
      // work must adjust placement. Do not equate this with complete routing.
      try(var stream=Files.newOutputStream(output)){SesWriter.write(board,stream,input.getFileName().toString());}
      System.out.println("Pass "+completed+": new escapes="+routed+", vias="+board.getVias().size());
      if(routed==0)break;
    }
    var report=new LinkedHashMap<String,Object>();report.put("driver","Targeted public-API fanout; official FreeRouting 2.5.0 JAR unchanged");report.put("components",seen);report.put("connected_smd_pins",pins.size());report.put("passes_completed",completed);report.put("settings",settings);report.put("attempts",attempts);report.put("manufacturing_ready",false);
    Files.writeString(output.resolveSibling(output.getFileName()+".json"),gson.toJson(report)+"\n");
  }
}
